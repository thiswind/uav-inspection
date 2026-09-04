import os
import uuid
import shutil
import csv
import io
import zipfile
import math
import asyncio
import json
from typing import List, Optional
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Query, HTTPException
from pydantic import BaseModel, Field
from datetime import datetime
from fastapi.responses import JSONResponse, StreamingResponse
from heatmapapp.utils.srt_parser import parse_dji_srt_file
from heatmapapp.services.ai_inference import engine
from heatmapapp.services.task_manager import task_manager, TaskStatus
from uav_url_prefix import prefixed
from deployment_paths import backend_path
router = APIRouter()
DATA_DIR = backend_path("heatmapdata", "videos")


class RenameTaskRequest(BaseModel):
    taskName: str = Field(min_length=1, max_length=80)


def _task_paths(task_id: str) -> tuple[Path, Path, Path]:
    if not task_id or task_id in {".", ".."} or "/" in task_id or "\\" in task_id:
        raise HTTPException(status_code=400, detail="无效的任务编号")
    return (
        DATA_DIR / f"{task_id}.mp4",
        DATA_DIR / f"{task_id}.srt",
        DATA_DIR / f"{task_id}.json",
    )


def _read_task_name(task_id: str) -> str | None:
    _, _, meta_path = _task_paths(task_id)
    try:
        payload = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return None
    task_name = str(payload.get("taskName") or "").strip()
    return task_name or None


def _write_task_name(task_id: str, task_name: str) -> None:
    _, _, meta_path = _task_paths(task_id)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    temp_path = meta_path.with_suffix(".json.tmp")
    temp_path.write_text(
        json.dumps({"taskId": task_id, "taskName": task_name}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temp_path.replace(meta_path)

@router.get("")
async def get_tasks():
    """扫描磁盘，将视频和SRT文件收编为前端可读的任务列表"""
    if not os.path.exists(DATA_DIR):
        return {"code": 200, "data": [], "message": "no data dir"}

    files = os.listdir(DATA_DIR)
    mp4_files = [f for f in files if f.lower().endswith(".mp4")]
    
    tasks = []
    for f in mp4_files:
        task_id = os.path.splitext(f)[0]
        srt_file = f"{task_id}.srt"
        
        # 获取文件修改时间
        mtime = os.path.getmtime(os.path.join(DATA_DIR, f))
        time_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
        
        stored = task_manager.get_task(task_id)
        # 优先从 task_manager 取状态；如果没有记录，检查引擎是否已有推理结果
        if stored:
            status = stored["status"]
            progress = stored.get("progress", 0)
        else:
            engine_result = engine.get_task_result(task_id)
            if engine_result and engine_result.get("isCompleted"):
                status = TaskStatus.COMPLETED
                progress = 100
            else:
                status = TaskStatus.PENDING
                progress = 0
        default_name = f"巡检任务_{task_id}"
        task_name = _read_task_name(task_id) or (stored or {}).get("taskName") or default_name
        tasks.append({
            "taskId": task_id,
            "taskName": task_name,
            "status": status,
            "progress": progress,
            "uploadTime": time_str,
            "videoUrl": prefixed(f"/api/v1/media/{f}"),
            "srtUrl": prefixed(f"/api/v1/media/{srt_file}") if srt_file in files else None
        })
    
    # 最新的排前面
    tasks.sort(key=lambda x: x["uploadTime"], reverse=True)
    return {"code": 200, "data": tasks, "message": "success"}

def _sync_save_file(source, dest_path: str):
    """在线程池中执行同步文件写入，避免阻塞事件循环"""
    with open(dest_path, "wb") as f:
        shutil.copyfileobj(source, f)

@router.post("/upload")
async def upload_task(video: UploadFile = File(...), srt: Optional[UploadFile] = File(None)):
    """处理大文件上传保存，SRT 遥测文件可选。文件写入在线程池中执行，不阻塞事件循环。"""
    task_id = f"task_{uuid.uuid4().hex[:6]}"
    os.makedirs(DATA_DIR, exist_ok=True)

    video_path, srt_path, _ = _task_paths(task_id)

    # 大文件写入在线程池中执行，不阻塞 asyncio 事件循环
    await asyncio.to_thread(_sync_save_file, video.file, video_path)
    if srt and srt.filename:
        await asyncio.to_thread(_sync_save_file, srt.file, srt_path)

    task_name = f"巡检任务_{task_id}"
    _write_task_name(task_id, task_name)
    task_manager.create_task(task_id, task_name)
    task_manager.update_status(task_id, TaskStatus.PROCESSING, progress=0)
    inference_available = engine.start_processing(task_id)
    return {
        "code": 200,
        "data": {"taskId": task_id, "inferenceAvailable": inference_available},
        "message": "success" if inference_available else f"上传成功；{engine.model_error}",
    }


@router.post("/{task_id}/rename")
async def rename_task(task_id: str, payload: RenameTaskRequest):
    video_path, _, _ = _task_paths(task_id)
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="任务不存在")

    task_name = payload.taskName.strip()
    if not task_name:
        raise HTTPException(status_code=400, detail="任务名称不能为空")

    await asyncio.to_thread(_write_task_name, task_id, task_name)
    task_manager.rename_task(task_id, task_name)
    return {
        "code": 200,
        "data": {"taskId": task_id, "taskName": task_name},
        "message": "任务已重命名",
    }


@router.delete("/{task_id}")
async def delete_task(task_id: str):
    video_path, srt_path, meta_path = _task_paths(task_id)
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="任务不存在")

    await engine.discard_task(task_id)

    def remove_task_files() -> None:
        for path in (video_path, srt_path, meta_path):
            if path.exists():
                path.unlink()

    try:
        await asyncio.to_thread(remove_task_files)
    except PermissionError as exc:
        raise HTTPException(status_code=409, detail="任务文件正在使用中，请稍后重试") from exc

    task_manager.delete_task(task_id)
    return {
        "code": 200,
        "data": {"taskId": task_id},
        "message": "任务已删除",
    }

@router.get("/{task_id}/status")
async def get_task_status(task_id: str):
    stored = task_manager.get_task(task_id)
    if not stored:
        video_path = os.path.join(DATA_DIR, f"{task_id}.mp4")
        if os.path.exists(video_path):
            # 文件存在但从未被推理过 → 待处理
            engine_result = engine.get_task_result(task_id)
            is_done = engine_result and engine_result.get("isCompleted")
            return {
                "code": 200,
                "data": {
                    "taskId": task_id,
                    "status": TaskStatus.COMPLETED if is_done else TaskStatus.PENDING,
                    "progress": 100 if is_done else 0,
                    "error": None,
                    "isCompleted": bool(is_done)
                },
                "message": "success"
            }
        return {"code": 404, "message": "任务不存在"}

    status = stored.get("status", TaskStatus.PENDING)
    progress = stored.get("progress", 0)
    return {
        "code": 200,
        "data": {
            "taskId": task_id,
            "status": status,
            "progress": progress,
            "error": stored.get("error"),
            "isCompleted": status == TaskStatus.COMPLETED
        },
        "message": "success"
    }

@router.get("/{task_id}/result")
async def get_task_result(task_id: str):
    try:
        engine.ensure_model()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    try:
        # 处理结果优先从引擎内存读取
        result = engine.get_task_result(task_id)
        if result is None:
            engine.start_processing(task_id)
            # SRT 可选：有则解析遥测，无则返回空
            srt_path = os.path.join(DATA_DIR, f"{task_id}.srt")
            telemetry_dict = parse_dji_srt_file(srt_path) if os.path.exists(srt_path) else {}
            result = {
                "fps": 30.0,
                "totalFrames": len(telemetry_dict),
                "telemetryData": list(telemetry_dict.values()),
                "trackingData": {},
                "alerts": [],
                "frameCounts": {},
                "isCompleted": False
            }

        if not result.get("isCompleted", False):
            engine.start_processing(task_id)

        history, prediction = _build_minute_stats(result.get("frameCounts", {}), result.get("fps", 30.0))

        return {
            "code": 200,
            "data": {
                "fps": result.get("fps", 30.0),
                "totalFrames": result.get("totalFrames", 0),
                "telemetryData": result.get("telemetryData", []),
                "trackingData": result.get("trackingData", {}),
                "alerts": result.get("alerts", []),
                "historyChartData": history,
                "predictChartData": prediction,
                "isCompleted": result.get("isCompleted", False)
            },
            "message": "success"
        }
    except Exception as e:
        return {"code": 500, "message": f"解析失败: {str(e)}"}


@router.get("/{task_id}/export")
async def export_task_report(
    task_id: str,
    include_minute: bool = Query(True),
    include_alerts: bool = Query(True)
):
    result = engine.get_task_result(task_id)
    if result is None:
        return JSONResponse(status_code=404, content={"message": "任务尚未完成或不存在"})

    if not include_minute and not include_alerts:
        return JSONResponse(status_code=400, content={"message": "请选择导出内容"})

    history, _prediction = _build_minute_stats(result.get("frameCounts", {}), result.get("fps", 30.0))
    alerts = result.get("alerts", [])

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        if include_minute:
            minute_csv = _build_minute_csv(history)
            zip_file.writestr("minute_stats.csv", minute_csv)
        if include_alerts:
            alert_csv = _build_alert_csv(alerts)
            zip_file.writestr("alerts.csv", alert_csv)

    zip_buffer.seek(0)
    headers = {
        "Content-Disposition": f"attachment; filename=heatmap_{task_id}.zip"
    }
    return StreamingResponse(zip_buffer, media_type="application/zip", headers=headers)


def _build_minute_stats(frame_counts: dict, fps: float, predict_minutes: int = 5):
    if fps <= 0:
        fps = 30.0
    frames_per_minute = int(fps * 60)

    if not frame_counts:
        history = []
        prediction = [None] * predict_minutes
        return history, prediction

    normalized = {int(k): v for k, v in frame_counts.items()}
    max_frame = max(normalized.keys())
    total_minutes = max(1, int(math.ceil(max_frame / frames_per_minute)))
    history: List[int] = []

    for minute_idx in range(total_minutes):
        start = minute_idx * frames_per_minute + 1
        end = (minute_idx + 1) * frames_per_minute
        counts = [normalized.get(f, 0) for f in range(start, end + 1)]
        if counts:
            history.append(int(sum(counts) / len(counts)))
        else:
            history.append(0)

    prediction = _linear_predict(history, predict_minutes)
    return history, prediction


def _linear_predict(history: List[int], predict_minutes: int):
    if not history:
        return [None] * predict_minutes

    n = len(history)
    x = list(range(n))
    y = history
    x_mean = sum(x) / n
    y_mean = sum(y) / n
    denom = sum((xi - x_mean) ** 2 for xi in x) or 1
    slope = sum((xi - x_mean) * (yi - y_mean) for xi, yi in zip(x, y)) / denom
    intercept = y_mean - slope * x_mean

    prediction = [None] * n
    for i in range(1, predict_minutes + 1):
        value = slope * (n - 1 + i) + intercept
        prediction.append(max(0, int(round(value))))
    return prediction


def _build_minute_csv(history: List[int]) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["minute", "avg_count"])
    for idx, value in enumerate(history, start=1):
        writer.writerow([idx, value])
    return output.getvalue()


def _build_alert_csv(alerts: List[dict]) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "timestamp", "frameId", "count", "threshold", "centerLat", "centerLon", "snapshotUrl"])
    for alert in alerts:
        writer.writerow([
            alert.get("id"),
            alert.get("timestamp"),
            alert.get("frameId"),
            alert.get("count"),
            alert.get("threshold"),
            alert.get("centerLat"),
            alert.get("centerLon"),
            alert.get("snapshotUrl")
        ])
    return output.getvalue()

