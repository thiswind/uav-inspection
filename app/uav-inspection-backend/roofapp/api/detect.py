import json
import os
import re
import shutil
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from deployment_paths import backend_path
from uav_url_prefix import prefixed

router = APIRouter()

ROOF_MEDIA_DIR = str(backend_path("roofdata", "media"))
ROOF_REPORTS_DIR = str(backend_path("roofdata", "reports"))
DEFAULT_TASK_NAME = "建筑屋顶巡检演示任务"

for path in [ROOF_MEDIA_DIR, ROOF_REPORTS_DIR]:
    os.makedirs(path, exist_ok=True)


def _task_dir(task_id: str) -> str:
    return os.path.join(ROOF_MEDIA_DIR, task_id)


def _report_dir(task_id: str) -> str:
    return os.path.join(ROOF_REPORTS_DIR, task_id)


def _load_json(path: str, default: Any) -> Any:
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def _save_json(path: str, payload: Any) -> None:
    with open(path, "w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)


def _pick_video_filename(task_id: str) -> str:
    task_dir = _task_dir(task_id)
    if not os.path.isdir(task_dir):
        return ""
    for filename in sorted(os.listdir(task_dir)):
        if filename.lower().endswith((".mp4", ".mov", ".avi", ".mkv")) and "annotated" not in filename.lower():
            return filename
    return ""


def _pick_srt_filename(task_id: str) -> str:
    task_dir = _task_dir(task_id)
    if not os.path.isdir(task_dir):
        return ""
    for filename in sorted(os.listdir(task_dir)):
        if filename.lower().endswith(".srt"):
            return filename
    return ""


def _load_task_meta(task_id: str) -> dict[str, Any]:
    return _load_json(os.path.join(_task_dir(task_id), "task.json"), {})


def _safe_stem(name: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z._-]+", "_", os.path.splitext(name)[0]).strip("._-")
    return cleaned or "video"


def _read_task(task_id: str) -> dict[str, Any]:
    task_dir = _task_dir(task_id)
    report_dir = _report_dir(task_id)
    if not os.path.isdir(task_dir):
        raise HTTPException(status_code=404, detail="屋顶巡检任务不存在")

    meta = _load_task_meta(task_id)
    defects = _load_json(os.path.join(report_dir, "defects.json"), [])
    telemetry = _load_json(os.path.join(report_dir, "telemetry.json"), [])
    storage_video_name = _pick_video_filename(task_id)
    srt_name = _pick_srt_filename(task_id)
    report_html = os.path.join(report_dir, "report.html")

    created_at = meta.get("created_at", "2026-06-04 15:29:04")
    updated_at = meta.get("updated_at", created_at)
    has_report = bool(defects or telemetry or os.path.exists(report_html))

    return {
        "id": task_id,
        "name": meta.get("name", DEFAULT_TASK_NAME),
        "status": meta.get("status", "completed" if has_report else "uploaded"),
        "progress": 100,
        "defect_count": len(defects),
        "video_url": prefixed(f"/api/v1/roof/media/{task_id}/{storage_video_name}") if storage_video_name else "",
        "srt_url": prefixed(f"/api/v1/roof/media/{task_id}/{srt_name}") if srt_name else "",
        "report_url": prefixed(f"/api/v1/roof/reports/{task_id}/report.html") if os.path.exists(report_html) else "",
        "created_at": created_at,
        "updated_at": updated_at,
        "duration_sec": round((telemetry[-1]["video_time_ms"] / 1000), 1) if telemetry else 0,
        "video_name": meta.get("video_name", storage_video_name),
        "srt_name": srt_name,
    }


def _sanitize_defect(defect: dict[str, Any]) -> dict[str, Any]:
    class_names = {
        "杂草堆积": "杂草堆积",
        "屋面脱皮": "屋面脱皮",
        "积水区域": "积水区域",
        "閺夊倽宕?": "杂草堆积",
        "閼磋京姣?": "屋面脱皮",
        "缁夘垱鎸?": "积水区域",
    }
    class_name = defect.get("class_name", "屋面缺陷")
    return {
        **defect,
        "class_name": class_names.get(class_name, class_name),
    }


@router.get("/tasks")
async def get_roof_tasks():
    task_ids = [
        name
        for name in sorted(os.listdir(ROOF_MEDIA_DIR))
        if os.path.isdir(os.path.join(ROOF_MEDIA_DIR, name))
    ]
    tasks = [_read_task(task_id) for task_id in task_ids]
    return {"tasks": tasks}


@router.post("/tasks/upload")
async def upload_roof_task(
    task_name: str = Form(""),
    video: UploadFile = File(...),
):
    original_name = video.filename or "roof-task.mp4"
    task_id = uuid.uuid4().hex[:12]
    task_dir = _task_dir(task_id)
    report_dir = _report_dir(task_id)
    os.makedirs(task_dir, exist_ok=True)
    os.makedirs(report_dir, exist_ok=True)

    stored_name = f"{_safe_stem(original_name)}{os.path.splitext(original_name)[1] or '.mp4'}"
    target_path = os.path.join(task_dir, stored_name)
    with open(target_path, "wb") as target:
        shutil.copyfileobj(video.file, target)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _save_json(
        os.path.join(task_dir, "task.json"),
        {
            "name": task_name or os.path.splitext(original_name)[0],
            "video_name": original_name,
            "status": "uploaded",
            "created_at": now,
            "updated_at": now,
        },
    )

    return {"task_id": task_id}


@router.get("/tasks/{task_id}")
async def get_roof_task(task_id: str):
    return _read_task(task_id)


@router.get("/tasks/{task_id}/defects")
async def get_roof_defects(task_id: str):
    _read_task(task_id)
    defects = _load_json(os.path.join(_report_dir(task_id), "defects.json"), [])
    return {"defects": [_sanitize_defect(item) for item in defects]}


@router.get("/tasks/{task_id}/statistics")
async def get_roof_statistics(task_id: str):
    _read_task(task_id)
    defects = _load_json(os.path.join(_report_dir(task_id), "defects.json"), [])
    summary = {
        "total": len(defects),
        "by_severity": {"high": 0, "medium": 0, "low": 0},
        "by_type": {},
        "by_status": {},
    }
    for raw_item in defects:
        item = _sanitize_defect(raw_item)
        severity = item.get("severity", "low")
        review_status = item.get("review_status", "pending")
        class_name = item.get("class_name", "未分类缺陷")
        summary["by_severity"][severity] = summary["by_severity"].get(severity, 0) + 1
        summary["by_type"][class_name] = summary["by_type"].get(class_name, 0) + 1
        summary["by_status"][review_status] = summary["by_status"].get(review_status, 0) + 1
    return summary


@router.get("/tasks/{task_id}/trajectory")
async def get_roof_trajectory(task_id: str):
    _read_task(task_id)
    telemetry = _load_json(os.path.join(_report_dir(task_id), "telemetry.json"), [])
    points = [[item["longitude"], item["latitude"]] for item in telemetry if "longitude" in item and "latitude" in item]
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": points},
                "properties": {"task_id": task_id},
            }
        ],
    }


@router.get("/tasks/{task_id}/map-meta")
async def get_roof_map_meta(task_id: str):
    _read_task(task_id)
    telemetry = _load_json(os.path.join(_report_dir(task_id), "telemetry.json"), [])
    if not telemetry:
        return {"center": [24.8334, 102.8399], "zoom": 18}
    center = telemetry[len(telemetry) // 2]
    return {
        "center": [center.get("latitude", 24.8334), center.get("longitude", 102.8399)],
        "zoom": 19,
    }


@router.get("/tasks/{task_id}/telemetry")
async def get_roof_telemetry(task_id: str):
    _read_task(task_id)
    telemetry = _load_json(os.path.join(_report_dir(task_id), "telemetry.json"), [])
    return {"telemetry": telemetry}


@router.put("/defects/{defect_id}/review")
async def review_roof_defect(defect_id: str, payload: dict[str, Any]):
    for task_id in os.listdir(ROOF_REPORTS_DIR):
        defects_path = os.path.join(_report_dir(task_id), "defects.json")
        defects = _load_json(defects_path, [])
        updated = False
        for defect in defects:
            if defect.get("id") == defect_id:
                defect["review_status"] = payload.get("review_status", defect.get("review_status", "pending"))
                updated = True
                break
        if updated:
            _save_json(defects_path, defects)
            return {"ok": True}
    raise HTTPException(status_code=404, detail="缺陷记录不存在")


@router.get("/health")
async def roof_health():
    task_count = len([name for name in os.listdir(ROOF_MEDIA_DIR) if os.path.isdir(os.path.join(ROOF_MEDIA_DIR, name))])
    return {"status": "ready", "tasks": task_count}
