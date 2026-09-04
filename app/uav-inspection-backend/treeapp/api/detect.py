from __future__ import annotations

import json
import re
import shutil
import subprocess
import uuid
from datetime import datetime
from functools import lru_cache
from pathlib import Path

import cv2
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from treeapp.detector import MODEL_PATH, tree_pruning_detector
from deployment_paths import backend_path
from optional_inference import inference_dependencies_available
from uav_url_prefix import prefixed

router = APIRouter()

MEDIA_DIR = backend_path('treedata', 'media')
MEDIA_DIR.mkdir(parents=True, exist_ok=True)
META_SUFFIX = '.task.json'
SUPPORTED_VIDEO_SUFFIXES = {'.mp4', '.avi', '.mov', '.mkv'}
BROWSER_READY_CODECS = {'h264', 'avc1'}
TRANSCODE_FOURCC_CANDIDATES = ('avc1', 'H264', 'X264')
FFMPEG_ENCODER_CANDIDATES = ('h264_nvenc', 'libx264')


class TreePruningDetectRequest(BaseModel):
    image: str
    conf: float | None = None
    iou: float | None = None


class TreePruningConfigRequest(BaseModel):
    confidence: float | None = None
    iou: float | None = None


class TreePruningImportPathRequest(BaseModel):
    task_name: str = ''
    video_path: str


def _meta_path(video_path: Path) -> Path:
    return video_path.with_name(f'{video_path.name}{META_SUFFIX}')


def _load_task_meta(video_path: Path) -> dict[str, str]:
    meta_file = _meta_path(video_path)
    if not meta_file.exists():
        return {}
    try:
        return json.loads(meta_file.read_text(encoding='utf-8'))
    except Exception:
        return {}


def _safe_stem(name: str) -> str:
    cleaned = re.sub(r'[^0-9A-Za-z._-]+', '_', Path(name).stem).strip('._-')
    return cleaned or 'video'


def _is_supported_video(video_path: Path) -> bool:
    return video_path.suffix.lower() in SUPPORTED_VIDEO_SUFFIXES


def _write_task_meta(target_path: Path, task_id: str, task_name: str, original_name: str) -> dict[str, str]:
    meta = {
        'task_id': task_id,
        'task_name': task_name or Path(original_name).stem,
        'video_name': original_name,
        'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    }
    _meta_path(target_path).write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8')
    return meta


def _serialize_task(video_path: Path, meta: dict[str, str], *, transcoded: bool | None = None, playback_codec: str | None = None) -> dict[str, object]:
    version = int(video_path.stat().st_mtime)
    display_name = meta.get('video_name', video_path.name)
    data: dict[str, object] = {
        'id': meta.get('task_id', video_path.stem),
        'name': display_name,
        'task_name': meta.get('task_name', Path(display_name).stem),
        'created_at': meta.get('created_at', ''),
        'source': 'upload' if meta.get('task_id') else 'system',
        'url': prefixed(f'/api/v1/pruning/media/{video_path.name}?v={version}'),
    }
    if transcoded is not None:
        data['transcoded'] = transcoded
    if playback_codec:
        data['playback_codec'] = playback_codec
    return data


def _collect_tasks() -> list[dict[str, object]]:
    tasks: list[dict[str, object]] = []
    if not MEDIA_DIR.exists():
        return []

    for file in MEDIA_DIR.iterdir():
        if not file.is_file() or not _is_supported_video(file):
            continue
        lower_name = file.name.lower()
        if (
            'source_mp4v' in lower_name
            or '__source' in file.stem.lower()
            or lower_name.startswith('_transcode_probe_')
        ):
            continue

        meta = _load_task_meta(file)
        item = _serialize_task(file, meta)
        tasks.append({
            **item,
            '_sort_group': 0 if item['source'] == 'upload' else 1,
            '_sort_time': file.stat().st_mtime,
        })

    tasks.sort(
        key=lambda item: (
            int(item['_sort_group']),
            -float(item['_sort_time']),
            str(item['task_name']).lower(),
        ),
    )

    return [
        {
            'id': item['id'],
            'name': item['name'],
            'task_name': item['task_name'],
            'created_at': item['created_at'],
            'source': item['source'],
            'url': item['url'],
        }
        for item in tasks
    ]


def _build_upload_paths(original_name: str) -> tuple[str, Path, Path]:
    task_id = uuid.uuid4().hex[:12]
    safe_stem = _safe_stem(original_name)
    source_suffix = Path(original_name).suffix or '.mp4'
    raw_path = MEDIA_DIR / f'{task_id}_{safe_stem}__source{source_suffix}'
    playback_path = MEDIA_DIR / f'{task_id}_{safe_stem}.mp4'
    return task_id, raw_path, playback_path


def _read_video_profile(video_path: Path) -> tuple[str, float, tuple[int, int]]:
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise RuntimeError(f'无法读取视频文件: {video_path.name}')

    fourcc_value = int(capture.get(cv2.CAP_PROP_FOURCC))
    codec = ''.join(chr((fourcc_value >> (8 * index)) & 0xFF) for index in range(4)).replace('\x00', '').strip().lower()
    fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    capture.release()

    if width <= 0 or height <= 0:
        raise RuntimeError(f'视频尺寸无效: {video_path.name}')

    return codec, fps, (width, height)


def _create_h264_writer(target_path: Path, fps: float, frame_size: tuple[int, int]) -> cv2.VideoWriter:
    for fourcc_name in TRANSCODE_FOURCC_CANDIDATES:
        writer = cv2.VideoWriter(str(target_path), cv2.VideoWriter_fourcc(*fourcc_name), fps, frame_size)
        if writer.isOpened():
            return writer
        writer.release()
    raise RuntimeError('浏览器兼容视频转码器初始化失败')


@lru_cache(maxsize=1)
def _find_ffmpeg_executable() -> str | None:
    direct_match = shutil.which('ffmpeg')
    if direct_match:
        return direct_match

    conda_prefix = Path.home() / '.conda'
    candidates = [
        Path('C:/Program Files/EVCapture/ffmpeg.exe'),
        *(conda_prefix / 'envs').glob('*/Library/bin/ffmpeg.exe'),
        *(conda_prefix / 'pkgs').glob('ffmpeg*/Library/bin/ffmpeg.exe'),
    ]

    for candidate in candidates:
        if candidate.exists():
            return str(candidate)

    return None


def _transcode_with_ffmpeg(source_path: Path, target_path: Path) -> tuple[bool, str]:
    ffmpeg_path = _find_ffmpeg_executable()
    if not ffmpeg_path:
        return False, ''

    temp_target = target_path.with_name(f'{target_path.stem}.tmp.mp4')
    last_error = ''

    for encoder in FFMPEG_ENCODER_CANDIDATES:
        if temp_target.exists():
            temp_target.unlink()

        command = [
            ffmpeg_path,
            '-y',
            '-hide_banner',
            '-loglevel',
            'error',
            '-i',
            str(source_path),
            '-map',
            '0:v:0',
            '-an',
            '-movflags',
            '+faststart',
            '-pix_fmt',
            'yuv420p',
        ]

        if encoder == 'h264_nvenc':
            command.extend(['-c:v', 'h264_nvenc', '-preset', 'p4', '-rc', 'vbr', '-cq', '28', '-b:v', '0'])
        else:
            command.extend(['-c:v', 'libx264', '-preset', 'veryfast', '-crf', '23'])

        command.append(str(temp_target))

        result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', errors='ignore')
        if result.returncode != 0:
            last_error = (result.stderr or result.stdout or f'{encoder} failed').strip()
            continue

        if not temp_target.exists() or temp_target.stat().st_size <= 0:
            last_error = f'{encoder} produced no output'
            continue

        codec, _, _ = _read_video_profile(temp_target)
        if codec not in BROWSER_READY_CODECS:
            last_error = f'{encoder} produced unsupported codec: {codec or "unknown"}'
            temp_target.unlink()
            continue

        if target_path.exists():
            target_path.unlink()
        temp_target.replace(target_path)
        return True, codec

    if temp_target.exists():
        temp_target.unlink()

    return False, last_error


def _transcode_to_browser_video(source_path: Path, target_path: Path) -> str:
    ffmpeg_success, ffmpeg_result = _transcode_with_ffmpeg(source_path, target_path)
    if ffmpeg_success:
        return ffmpeg_result

    capture = cv2.VideoCapture(str(source_path))
    if not capture.isOpened():
        raise RuntimeError(f'无法读取上传视频: {source_path.name}')

    fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    if width <= 0 or height <= 0:
        capture.release()
        raise RuntimeError('上传视频缺少有效画面尺寸')

    safe_fps = fps if 1.0 <= fps <= 120.0 else 25.0
    temp_target = target_path.with_name(f'{target_path.stem}.tmp.mp4')
    if temp_target.exists():
        temp_target.unlink()

    writer = _create_h264_writer(temp_target, safe_fps, (width, height))
    frame_count = 0
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            writer.write(frame)
            frame_count += 1
    finally:
        capture.release()
        writer.release()

    if frame_count == 0 or not temp_target.exists() or temp_target.stat().st_size <= 0:
        if temp_target.exists():
            temp_target.unlink()
        raise RuntimeError('上传视频没有可转码的有效帧')

    codec, _, _ = _read_video_profile(temp_target)
    if codec not in BROWSER_READY_CODECS:
        temp_target.unlink()
        raise RuntimeError(f'转码后视频仍不是浏览器可播放格式: {codec or "unknown"}')

    if target_path.exists():
        target_path.unlink()
    temp_target.replace(target_path)
    return codec


def _normalize_uploaded_video(raw_path: Path, playback_path: Path) -> tuple[bool, str]:
    codec, _, _ = _read_video_profile(raw_path)
    if codec in BROWSER_READY_CODECS and raw_path.suffix.lower() == '.mp4':
        if playback_path.exists():
            playback_path.unlink()
        raw_path.replace(playback_path)
        return False, codec

    raise RuntimeError('Only MP4 videos encoded with H.264/AVC1 can be uploaded.')


def _store_uploaded_video(raw_path: Path, playback_path: Path) -> tuple[bool, str]:
    try:
        return _normalize_uploaded_video(raw_path, playback_path)
    finally:
        if raw_path.exists():
            raw_path.unlink()


def _ensure_browser_ready_video(video_path: Path) -> tuple[bool, str]:
    codec, _, _ = _read_video_profile(video_path)
    if codec in BROWSER_READY_CODECS and video_path.suffix.lower() == '.mp4':
        return False, codec

    legacy_source = video_path.with_name(f'{video_path.stem}.__legacy_source{video_path.suffix}')
    if legacy_source.exists():
        legacy_source.unlink()
    shutil.copy2(video_path, legacy_source)

    try:
        playback_codec = _transcode_to_browser_video(legacy_source, video_path)
    finally:
        if legacy_source.exists():
            legacy_source.unlink()

    return True, playback_codec


@router.get('/health')
async def pruning_health() -> dict[str, object]:
    model_exists = tree_pruning_detector.is_model_available()
    inference_available = model_exists and inference_dependencies_available()
    return {
        'code': 200,
        'message': 'success' if inference_available else '基础服务正常，可选 AI 推理暂不可用',
        'data': {
            'status': 'ready' if inference_available else 'not_ready',
            'service_status': 'running',
            'inference_available': inference_available,
            'model': MODEL_PATH.name,
            'loaded': tree_pruning_detector.model is not None,
            'device': tree_pruning_detector.device,
            'error': '' if inference_available else '请安装 02-data 中的乔木模型及 requirements-inference.txt；文件上传和播放不受影响。',
        },
    }


@router.get('/videos')
async def pruning_videos() -> dict[str, object]:
    return {'code': 200, 'message': 'success', 'data': {'videos': _collect_tasks()}}


@router.post('/tasks/upload')
async def pruning_upload_task(
    task_name: str = Form(''),
    video: UploadFile = File(...),
) -> dict[str, object]:
    original_name = video.filename or 'pruning-task.mp4'
    if not _is_supported_video(Path(original_name)):
        raise HTTPException(status_code=400, detail='仅支持 mp4、avi、mov、mkv 视频文件')

    task_id, raw_path, playback_path = _build_upload_paths(original_name)
    with raw_path.open('wb') as target:
        shutil.copyfileobj(video.file, target)

    try:
        transcoded, playback_codec = _store_uploaded_video(raw_path, playback_path)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    meta = _write_task_meta(playback_path, task_id, task_name, original_name)
    task = _serialize_task(playback_path, meta, transcoded=transcoded, playback_codec=playback_codec)
    return {'code': 200, 'message': 'success', 'data': task}


@router.post('/tasks/import-path')
async def pruning_import_task_from_path(payload: TreePruningImportPathRequest) -> dict[str, object]:
    source_path = Path(payload.video_path).expanduser()
    if not source_path.exists() or not source_path.is_file():
        raise HTTPException(status_code=404, detail=f'视频文件不存在: {source_path}')
    if not _is_supported_video(source_path):
        raise HTTPException(status_code=400, detail='仅支持 mp4、avi、mov、mkv 视频文件')

    original_name = source_path.name
    task_id, raw_path, playback_path = _build_upload_paths(original_name)
    shutil.copy2(source_path, raw_path)

    try:
        transcoded, playback_codec = _store_uploaded_video(raw_path, playback_path)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    meta = _write_task_meta(playback_path, task_id, payload.task_name, original_name)
    task = _serialize_task(playback_path, meta, transcoded=transcoded, playback_codec=playback_codec)
    return {'code': 200, 'message': 'success', 'data': task}


@router.delete('/tasks/{task_id}')
async def pruning_delete_task(task_id: str) -> dict[str, object]:
    target_video: Path | None = None
    target_meta: dict[str, str] = {}

    if MEDIA_DIR.exists():
        for file in MEDIA_DIR.iterdir():
            if not file.is_file() or not _is_supported_video(file):
                continue
            meta = _load_task_meta(file)
            if meta.get('task_id') == task_id:
                target_video = file
                target_meta = meta
                break

    if target_video is None:
        raise HTTPException(status_code=404, detail='任务不存在或不支持删除')

    meta_path = _meta_path(target_video)
    if target_video.exists():
        target_video.unlink()
    if meta_path.exists():
        meta_path.unlink()

    return {
        'code': 200,
        'message': 'success',
        'data': {
            'task_id': task_id,
            'task_name': target_meta.get('task_name', task_id),
            'video_name': target_meta.get('video_name', target_video.name),
        },
    }


@router.get('/config')
async def pruning_config() -> dict[str, object]:
    return {'code': 200, 'message': 'success', 'data': tree_pruning_detector.update_config()}


@router.post('/config')
async def pruning_update_config(payload: TreePruningConfigRequest) -> dict[str, object]:
    return {
        'code': 200,
        'message': 'success',
        'data': tree_pruning_detector.update_config(confidence=payload.confidence, iou=payload.iou),
    }


@router.get('/info')
async def pruning_info() -> dict[str, object]:
    try:
        return {'code': 200, 'message': 'success', 'data': tree_pruning_detector.get_info()}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post('/detect')
async def pruning_detect(payload: TreePruningDetectRequest) -> JSONResponse:
    try:
        result = tree_pruning_detector.detect_base64(payload.image, conf_threshold=payload.conf, iou_threshold=payload.iou)
        return JSONResponse({'code': 200, 'message': 'success', 'data': result})
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
