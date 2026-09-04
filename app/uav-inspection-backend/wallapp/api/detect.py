from __future__ import annotations

import base64
import json
import re
import shutil
import uuid
from datetime import datetime
from pathlib import Path, PureWindowsPath
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from wallapp.detector import wall_detector
from wallapp.report import build_wall_assessment, generate_wall_report_pdf
from deployment_paths import backend_path
from uav_url_prefix import prefixed

router = APIRouter()

MEDIA_DIR = backend_path('walldata', 'media')
MEDIA_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR = backend_path('walldata', 'logs')
REPORTS_DIR = backend_path('walldata', 'reports')
LOGS_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
META_SUFFIX = '.task.json'
DATASET_DIR = backend_path('wallapp', 'wall_damage_dataset')
DATASET_METADATA = DATASET_DIR / 'metadata.json'
ANNOTATION_FPS = 30.0
SUPPORTED_VIDEO_SUFFIXES = {'.mp4', '.avi', '.mov', '.mkv', '.webm'}
SUPPORTED_SUBTITLE_SUFFIXES = {'.srt', '.txt', '.vtt'}


class WallDetectRequest(BaseModel):
    image: str
    conf: float | None = None
    iou: float | None = None


class WallConfigRequest(BaseModel):
    confidence: float | None = None
    iou: float | None = None


class WallRenameTaskRequest(BaseModel):
    task_name: str


class WallImportPathRequest(BaseModel):
    task_name: str = ''
    video_path: str
    subtitle_path: str


class WallDetectionLogRequest(BaseModel):
    time: float
    detections: list[dict[str, Any]]
    annotated_image: str
    image_size: dict[str, int] | None = None
    telemetry: dict[str, Any] | None = None


def _meta_path(video_path: Path) -> Path:
    return video_path.with_name(f'{video_path.name}{META_SUFFIX}')


def _task_log_dir(task_id: str) -> Path:
    target = (LOGS_DIR / re.sub(r'[^0-9A-Za-z_-]+', '_', task_id)).resolve()
    root = LOGS_DIR.resolve()
    if target == root or root not in target.parents:
        raise HTTPException(status_code=400, detail='任务编号不合法')
    return target


def _task_report_dir(task_id: str) -> Path:
    target = (REPORTS_DIR / re.sub(r'[^0-9A-Za-z_-]+', '_', task_id)).resolve()
    root = REPORTS_DIR.resolve()
    if target == root or root not in target.parents:
        raise HTTPException(status_code=400, detail='任务编号不合法')
    return target


def _logs_file(task_id: str) -> Path:
    return _task_log_dir(task_id) / 'logs.json'


def _read_logs(task_id: str) -> list[dict[str, Any]]:
    path = _logs_file(task_id)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding='utf-8-sig'))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _write_logs(task_id: str, logs: list[dict[str, Any]]) -> None:
    directory = _task_log_dir(task_id)
    directory.mkdir(parents=True, exist_ok=True)
    temporary = directory / 'logs.json.tmp'
    temporary.write_text(json.dumps(logs, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(directory / 'logs.json')


def _repair_log_labels(task_id: str, logs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    changed = False
    directory = _task_log_dir(task_id)
    for log in logs:
        if int(log.get('labels_version') or 0) >= 2:
            continue
        image_path = directory / str(log.get('image_file') or '')
        if image_path.is_file():
            try:
                repaired = wall_detector.normalize_log_image(image_path.read_bytes(), log.get('detections') or [])
                image_path.write_bytes(repaired)
            except Exception:
                continue
        log['labels_version'] = 2
        changed = True
    if changed:
        _write_logs(task_id, logs)
    return logs


def _subtitle_file(video_path: Path, meta: dict[str, Any]) -> Path | None:
    filename = str(meta.get('subtitle_file') or '')
    if not filename:
        return None
    path = MEDIA_DIR / filename
    return path if path.exists() else None


def _load_task_meta(video_path: Path) -> dict[str, str]:
    meta_file = _meta_path(video_path)
    if not meta_file.exists():
        return {}
    try:
        return json.loads(meta_file.read_text(encoding='utf-8-sig'))
    except Exception:
        return {}


def _safe_stem(name: str) -> str:
    cleaned = re.sub(r'[^0-9A-Za-z._-]+', '_', Path(name).stem).strip('._-')
    return cleaned or 'wall-video'


def _video_files() -> list[Path]:
    if not MEDIA_DIR.exists():
        return []
    return [
        file
        for file in sorted(MEDIA_DIR.iterdir(), key=lambda item: item.name)
        if file.suffix.lower() in {'.mp4', '.avi', '.mov', '.mkv', '.webm'}
    ]


def _serialize_video(file: Path) -> dict[str, object]:
    meta = _load_task_meta(file)
    version = int(file.stat().st_mtime)
    display_name = meta.get('video_name', file.name)
    subtitle_path = _subtitle_file(file, meta)
    return {
        'id': meta.get('task_id', file.stem),
        'name': display_name,
        'task_name': meta.get('task_name', Path(display_name).stem),
        'created_at': meta.get('created_at', ''),
        'source': meta.get('source', 'system'),
        'url': prefixed(f'/api/v1/wall/media/{file.name}?v={version}'),
        'start_at': float(meta.get('start_at', 0) or 0),
        'subtitle_name': meta.get('subtitle_name', ''),
        'subtitle_url': prefixed(f'/api/v1/wall/media/{subtitle_path.name}?v={int(subtitle_path.stat().st_mtime)}') if subtitle_path else '',
        'has_subtitle': bool(subtitle_path),
    }


def _find_video_by_task_id(task_id: str) -> Path:
    for file in _video_files():
        meta = _load_task_meta(file)
        if str(meta.get('task_id', file.stem)) == task_id:
            return file
    raise HTTPException(status_code=404, detail='任务不存在')


def _source_stem(value: object) -> str:
    source = str(value or '').split('#', 1)[0]
    if not source:
        return ''
    return PureWindowsPath(source).stem or Path(source).stem


def _resolve_dataset_file(value: object) -> Path:
    raw_path = Path(str(value or ''))
    if raw_path.exists():
        return raw_path
    return DATASET_DIR / raw_path


def _frame_from_source(source: object, fallback_name: str) -> int:
    source_text = str(source or '')
    if '#' in source_text:
        frame_text = source_text.rsplit('#', 1)[-1]
        if frame_text.isdigit():
            return int(frame_text)

    match = re.search(r'_(\d{4,})$', Path(fallback_name).stem)
    return int(match.group(1)) if match else 0


def _load_dataset_metadata() -> dict[str, object]:
    if not DATASET_METADATA.exists():
        return {}
    try:
        return json.loads(DATASET_METADATA.read_text(encoding='utf-8-sig'))
    except Exception:
        return {}


def _load_yolo_tile_spalling(label_path: Path) -> list[dict[str, object]]:
    if not label_path.exists():
        return []

    detections: list[dict[str, object]] = []
    for line in label_path.read_text(encoding='utf-8-sig').splitlines():
        parts = line.strip().split()
        if len(parts) < 5:
            continue
        try:
            cx, cy, width, height = (float(parts[index]) for index in range(1, 5))
        except ValueError:
            continue

        x1 = max(0.0, min(1.0, cx - width / 2))
        y1 = max(0.0, min(1.0, cy - height / 2))
        x2 = max(0.0, min(1.0, cx + width / 2))
        y2 = max(0.0, min(1.0, cy + height / 2))
        if x2 <= x1 or y2 <= y1:
            continue

        detections.append({
            'class': 2,
            'name': 'TileSpalling',
            'cn': '面砖脱落',
            'bbox': [x1, y1, x2, y2],
            'conf': 0.98,
        })
    return detections


@router.get('/health')
async def wall_health() -> dict[str, object]:
    try:
        wall_detector.load_model()
        info = wall_detector.get_info()
        return {
            'code': 200,
            'message': 'success',
            'data': {
                'status': 'ready',
                'service_status': 'running',
                'inference_available': True,
                'model': info['model']['name'],
                'mode': 'yolo' if info['model'].get('loaded') else 'rule_fallback',
            },
        }
    except Exception as exc:
        return {'code': 500, 'message': 'error', 'data': {'status': 'not_ready', 'error': str(exc)}}


@router.get('/videos')
async def wall_videos() -> dict[str, object]:
    videos = [_serialize_video(file) for file in _video_files()]
    return {'code': 200, 'message': 'success', 'data': {'videos': videos}}


@router.post('/tasks/upload')
async def wall_upload_task(
    task_name: str = Form(''),
    video: UploadFile = File(...),
    subtitle: UploadFile = File(...),
) -> dict[str, object]:
    original_name = video.filename or 'wall-task.mp4'
    if Path(original_name).suffix.lower() not in SUPPORTED_VIDEO_SUFFIXES:
        raise HTTPException(status_code=400, detail='仅支持 mp4、avi、mov、mkv、webm 视频文件')
    subtitle_name = subtitle.filename or ''
    if not subtitle_name:
        raise HTTPException(status_code=400, detail='必须上传与视频对应的字幕文件')
    if Path(subtitle_name).suffix.lower() not in SUPPORTED_SUBTITLE_SUFFIXES:
        raise HTTPException(status_code=400, detail='仅支持 srt、txt、vtt 字幕文件')
    task_id = uuid.uuid4().hex[:12]
    stored_name = f'{task_id}_{_safe_stem(original_name)}{Path(original_name).suffix or ".mp4"}'
    target_path = MEDIA_DIR / stored_name

    subtitle_file = f'{target_path.stem}_subtitle{Path(subtitle_name).suffix.lower()}'
    subtitle_target = MEDIA_DIR / subtitle_file
    try:
        with target_path.open('wb') as target:
            shutil.copyfileobj(video.file, target)
        with subtitle_target.open('wb') as target:
            shutil.copyfileobj(subtitle.file, target)
    except Exception as exc:
        target_path.unlink(missing_ok=True)
        subtitle_target.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f'上传任务保存失败: {exc}') from exc

    meta = {
        'task_id': task_id,
        'task_name': task_name or Path(original_name).stem,
        'video_name': original_name,
        'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'source': 'upload',
        'subtitle_name': subtitle_name,
        'subtitle_file': subtitle_file,
    }
    _meta_path(target_path).write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8')

    task = _serialize_video(target_path)
    task.update({'task_id': task_id, 'video_name': original_name})
    return {
        'code': 200,
        'message': 'success',
        'data': task,
    }


@router.post('/tasks/import-path')
async def wall_import_task_from_path(payload: WallImportPathRequest) -> dict[str, object]:
    source_path = Path(payload.video_path).expanduser().resolve()
    if not source_path.exists() or not source_path.is_file():
        raise HTTPException(status_code=404, detail=f'视频文件不存在: {source_path}')
    if source_path.suffix.lower() not in SUPPORTED_VIDEO_SUFFIXES:
        raise HTTPException(status_code=400, detail='仅支持 mp4、avi、mov、mkv、webm 视频文件')
    subtitle_path = Path(payload.subtitle_path).expanduser().resolve()
    if not subtitle_path.exists() or not subtitle_path.is_file():
        raise HTTPException(status_code=404, detail=f'字幕文件不存在: {subtitle_path}')
    if subtitle_path.suffix.lower() not in SUPPORTED_SUBTITLE_SUFFIXES:
        raise HTTPException(status_code=400, detail='仅支持 srt、txt、vtt 字幕文件')

    source_size = source_path.stat().st_size
    free_space = shutil.disk_usage(MEDIA_DIR).free
    subtitle_size = subtitle_path.stat().st_size
    if free_space < source_size + subtitle_size + 512 * 1024 * 1024:
        raise HTTPException(status_code=507, detail='Demo 内部目录磁盘空间不足，无法复制该视频')

    task_id = uuid.uuid4().hex[:12]
    stored_name = f'{task_id}_{_safe_stem(source_path.name)}{source_path.suffix or ".mp4"}'
    target_path = MEDIA_DIR / stored_name
    temporary_path = target_path.with_name(f'{target_path.name}.part')
    subtitle_file = f'{target_path.stem}_subtitle{subtitle_path.suffix.lower()}'
    subtitle_target = MEDIA_DIR / subtitle_file

    try:
        await run_in_threadpool(shutil.copy2, source_path, temporary_path)
        temporary_path.replace(target_path)
        await run_in_threadpool(shutil.copy2, subtitle_path, subtitle_target)
    except Exception as exc:
        if temporary_path.exists():
            temporary_path.unlink()
        target_path.unlink(missing_ok=True)
        subtitle_target.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f'复制视频失败: {exc}') from exc

    meta = {
        'task_id': task_id,
        'task_name': payload.task_name.strip() or source_path.stem,
        'video_name': source_path.name,
        'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'source': 'upload',
        'source_path': str(source_path),
        'import_mode': 'copy',
        'source_size': source_size,
        'subtitle_name': subtitle_path.name,
        'subtitle_file': subtitle_file,
    }
    _meta_path(target_path).write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8')
    return {'code': 200, 'message': 'success', 'data': _serialize_video(target_path)}


@router.post('/tasks/{task_id}/rename')
async def wall_rename_task(task_id: str, payload: WallRenameTaskRequest) -> dict[str, object]:
    task_name = payload.task_name.strip()
    if not task_name:
        raise HTTPException(status_code=400, detail='任务名称不能为空')

    video_path = _find_video_by_task_id(task_id)
    meta = _load_task_meta(video_path)
    meta.update({
        'task_id': meta.get('task_id', video_path.stem),
        'task_name': task_name,
        'video_name': meta.get('video_name', video_path.name),
        'created_at': meta.get('created_at', ''),
    })
    _meta_path(video_path).write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8')
    return {'code': 200, 'message': 'success', 'data': _serialize_video(video_path)}


@router.delete('/tasks/{task_id}')
async def wall_delete_task(task_id: str) -> dict[str, object]:
    video_path = _find_video_by_task_id(task_id)
    task = _serialize_video(video_path)
    meta_path = _meta_path(video_path)
    meta = _load_task_meta(video_path)
    subtitle_path = _subtitle_file(video_path, meta)

    video_path.unlink()
    if meta_path.exists():
        meta_path.unlink()
    if subtitle_path and subtitle_path.exists():
        subtitle_path.unlink()
    shutil.rmtree(_task_log_dir(task_id), ignore_errors=True)
    shutil.rmtree(_task_report_dir(task_id), ignore_errors=True)

    return {'code': 200, 'message': 'success', 'data': task}


@router.get('/tasks/{task_id}/annotations')
async def wall_task_annotations(task_id: str) -> dict[str, object]:
    video_path = _find_video_by_task_id(task_id)
    task_meta = _load_task_meta(video_path)
    dataset_meta = _load_dataset_metadata()
    source_stems = {
        _source_stem(task_meta.get('source')),
        _source_stem(task_meta.get('video_name')),
        _source_stem(video_path.name),
    }
    source_stems = {stem.lower() for stem in source_stems if stem}

    frames: list[dict[str, object]] = []
    for source_item in dataset_meta.get('sources', []):
        if not isinstance(source_item, dict):
            continue

        item_stem = _source_stem(source_item.get('source')).lower()
        if source_stems and item_stem not in source_stems:
            continue

        label_path = _resolve_dataset_file(source_item.get('label'))
        image_path = _resolve_dataset_file(source_item.get('image'))
        frame = _frame_from_source(source_item.get('source'), image_path.name)
        detections = _load_yolo_tile_spalling(label_path)
        frames.append({
            'frame': frame,
            'time': frame / ANNOTATION_FPS,
            'detections': detections,
        })

    frames.sort(key=lambda item: int(item['frame']))
    start_at = float(task_meta.get('start_at', 0) or 0)
    return {
        'code': 200,
        'message': 'success',
        'data': {
            'fps': ANNOTATION_FPS,
            'start_frame': int(round(start_at * ANNOTATION_FPS)),
            'frames': frames,
            'count': sum(len(frame['detections']) for frame in frames),
        },
    }


@router.get('/tasks/{task_id}/logs')
async def wall_task_logs(task_id: str) -> dict[str, object]:
    _find_video_by_task_id(task_id)
    logs = await run_in_threadpool(_repair_log_labels, task_id, _read_logs(task_id))
    return {
        'code': 200,
        'message': 'success',
        'data': {
            'logs': logs,
            'assessment': build_wall_assessment(logs),
        },
    }


@router.post('/tasks/{task_id}/logs')
async def wall_create_detection_log(task_id: str, payload: WallDetectionLogRequest) -> dict[str, object]:
    _find_video_by_task_id(task_id)
    if not payload.detections:
        raise HTTPException(status_code=400, detail='检测日志必须包含至少一个缺陷')
    encoded = payload.annotated_image.split(',', 1)[-1]
    try:
        image_bytes = base64.b64decode(encoded, validate=True)
    except Exception as exc:
        raise HTTPException(status_code=400, detail='检测日志图片格式不正确') from exc
    if not image_bytes or len(image_bytes) > 12 * 1024 * 1024:
        raise HTTPException(status_code=400, detail='检测日志图片为空或过大')
    try:
        image_bytes = await run_in_threadpool(wall_detector.normalize_log_image, image_bytes, payload.detections)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail='检测日志图片无法解析') from exc

    directory = _task_log_dir(task_id)
    directory.mkdir(parents=True, exist_ok=True)
    timestamp_ms = max(0, int(round(payload.time * 1000)))
    log_id = f'log_{timestamp_ms:010d}'
    image_file = f'{log_id}.jpg'
    (directory / image_file).write_bytes(image_bytes)
    entry = {
        'id': log_id,
        'time': round(float(payload.time), 3),
        'detections': payload.detections,
        'image_size': payload.image_size or {},
        'telemetry': payload.telemetry or {},
        'image_file': image_file,
        'image_url': prefixed(f'/api/v1/wall/tasks/{task_id}/logs/{log_id}/image'),
        'labels_version': 2,
        'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    }
    logs = [item for item in _read_logs(task_id) if item.get('id') != log_id]
    logs.append(entry)
    logs.sort(key=lambda item: float(item.get('time') or 0))
    if len(logs) > 180:
        removed = logs[:-180]
        logs = logs[-180:]
        for item in removed:
            old_image = directory / str(item.get('image_file') or '')
            if old_image.is_file():
                old_image.unlink()
    _write_logs(task_id, logs)
    return {'code': 200, 'message': 'success', 'data': entry}


@router.get('/tasks/{task_id}/logs/{log_id}/image')
async def wall_detection_log_image(task_id: str, log_id: str) -> FileResponse:
    _find_video_by_task_id(task_id)
    safe_id = re.sub(r'[^0-9A-Za-z_-]+', '', log_id)
    image_path = _task_log_dir(task_id) / f'{safe_id}.jpg'
    if not image_path.exists() or not image_path.is_file():
        raise HTTPException(status_code=404, detail='检测日志图片不存在')
    return FileResponse(image_path, media_type='image/jpeg')


@router.get('/tasks/{task_id}/assessment')
async def wall_task_assessment(task_id: str) -> dict[str, object]:
    _find_video_by_task_id(task_id)
    return {'code': 200, 'message': 'success', 'data': build_wall_assessment(_read_logs(task_id))}


@router.post('/tasks/{task_id}/report')
async def wall_export_pdf_report(task_id: str) -> FileResponse:
    video_path = _find_video_by_task_id(task_id)
    task = _serialize_video(video_path)
    logs = await run_in_threadpool(_repair_log_labels, task_id, _read_logs(task_id))
    assessment = build_wall_assessment(logs)
    output_dir = _task_report_dir(task_id)
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_path = output_dir / f'wall_report_{timestamp}.pdf'
    await run_in_threadpool(
        generate_wall_report_pdf,
        output_path,
        task,
        logs,
        assessment,
        _task_log_dir(task_id),
    )
    return FileResponse(
        output_path,
        media_type='application/pdf',
        filename=f'wall_inspection_report_{timestamp}.pdf',
    )


@router.get('/config')
async def wall_config() -> dict[str, object]:
    return {'code': 200, 'message': 'success', 'data': wall_detector.update_config()}


@router.post('/config')
async def wall_update_config(payload: WallConfigRequest) -> dict[str, object]:
    return {'code': 200, 'message': 'success', 'data': wall_detector.update_config(confidence=payload.confidence, iou=payload.iou)}


@router.get('/info')
async def wall_info() -> dict[str, object]:
    try:
        return {'code': 200, 'message': 'success', 'data': wall_detector.get_info()}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post('/detect')
async def wall_detect(payload: WallDetectRequest) -> JSONResponse:
    try:
        result = wall_detector.detect_base64(payload.image, conf_threshold=payload.conf, iou_threshold=payload.iou)
        return JSONResponse({'code': 200, 'message': 'success', 'data': result})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
