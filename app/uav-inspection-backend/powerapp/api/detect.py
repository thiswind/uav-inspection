from __future__ import annotations

import json
import re
import shutil
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from powerapp.detector import power_detector
from deployment_paths import backend_path
from uav_url_prefix import prefixed

router = APIRouter()

MEDIA_DIR = backend_path('powerdata', 'media')
MEDIA_DIR.mkdir(parents=True, exist_ok=True)
META_SUFFIX = '.task.json'


class PowerDetectRequest(BaseModel):
    image: str
    conf: float | None = None
    iou: float | None = None


class PowerConfigRequest(BaseModel):
    confidence: float | None = None
    iou: float | None = None


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


@router.get('/health')
async def power_health() -> dict[str, object]:
    try:
        power_detector.load_model()
        return {'code': 200, 'message': 'success', 'data': {'status': 'ready', 'service_status': 'running', 'inference_available': True, 'model': 'loaded'}}
    except Exception as exc:
        return {'code': 200, 'message': '基础服务正常，可选 AI 推理暂不可用', 'data': {'status': 'not_ready', 'service_status': 'running', 'inference_available': False, 'error': str(exc)}}


@router.get('/videos')
async def power_videos() -> dict[str, object]:
    videos = []
    if MEDIA_DIR.exists():
        for file in sorted(MEDIA_DIR.iterdir(), key=lambda item: item.name):
            if file.suffix.lower() in {'.mp4', '.avi', '.mov', '.mkv'}:
                meta = _load_task_meta(file)
                version = int(file.stat().st_mtime)
                display_name = meta.get('video_name', file.name)
                videos.append({
                    'id': meta.get('task_id', file.stem),
                    'name': display_name,
                    'task_name': meta.get('task_name', Path(display_name).stem),
                    'created_at': meta.get('created_at', ''),
                    'url': prefixed(f'/api/v1/power/media/{file.name}?v={version}'),
                })
    return {'code': 200, 'message': 'success', 'data': {'videos': videos}}


@router.post('/tasks/upload')
async def power_upload_task(
    task_name: str = Form(''),
    video: UploadFile = File(...),
) -> dict[str, object]:
    original_name = video.filename or 'power-task.mp4'
    task_id = uuid.uuid4().hex[:12]
    stored_name = f'{task_id}_{_safe_stem(original_name)}{Path(original_name).suffix or ".mp4"}'
    target_path = MEDIA_DIR / stored_name

    with target_path.open('wb') as target:
        shutil.copyfileobj(video.file, target)

    meta = {
        'task_id': task_id,
        'task_name': task_name or Path(original_name).stem,
        'video_name': original_name,
        'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    }
    _meta_path(target_path).write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8')

    version = int(target_path.stat().st_mtime)
    return {
        'code': 200,
        'message': 'success',
        'data': {
            'id': task_id,
            'task_id': task_id,
            'task_name': meta['task_name'],
            'video_name': original_name,
            'created_at': meta['created_at'],
            'url': prefixed(f'/api/v1/power/media/{stored_name}?v={version}'),
        },
    }


@router.get('/config')
async def power_config() -> dict[str, object]:
    return {'code': 200, 'message': 'success', 'data': power_detector.update_config()}


@router.post('/config')
async def power_update_config(payload: PowerConfigRequest) -> dict[str, object]:
    return {'code': 200, 'message': 'success', 'data': power_detector.update_config(confidence=payload.confidence, iou=payload.iou)}


@router.get('/info')
async def power_info() -> dict[str, object]:
    try:
        return {'code': 200, 'message': 'success', 'data': power_detector.get_info()}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post('/detect')
async def power_detect(payload: PowerDetectRequest) -> JSONResponse:
    try:
        result = power_detector.detect_base64(payload.image, conf_threshold=payload.conf, iou_threshold=payload.iou)
        return JSONResponse({'code': 200, 'message': 'success', 'data': result})
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
