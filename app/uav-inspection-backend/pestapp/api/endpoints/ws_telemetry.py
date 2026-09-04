"""遥测数据流 WebSocket — 基于 mock_track.json 逐秒推送"""
import json
import asyncio
import logging
import os
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pestapp.services.pest_service import PestService

router = APIRouter()
logger = logging.getLogger(__name__)

# 预加载遥测数据
_telemetry_cache: list[dict] = []
_cache_loaded = False


def _load_telemetry_cache():
    global _telemetry_cache, _cache_loaded
    if _cache_loaded:
        return
    base_dir = PestService._get_base_data_dir()
    file_path = os.path.join(base_dir, "mock_track.json")
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                _telemetry_cache = sorted(data, key=lambda x: x.get("video_time_sec", 0))
    except Exception as e:
        logger.info("Optional telemetry cache unavailable: %s", e)
        _telemetry_cache = []
    _cache_loaded = True


@router.websocket("/pest/telemetry")
async def pest_telemetry_stream(websocket: WebSocket):
    await websocket.accept()
    logger.info("Telemetry WebSocket connected")

    _load_telemetry_cache()

    index = 0
    try:
        while True:
            await asyncio.sleep(1.0)  # 每秒推送一条

            if _telemetry_cache:
                item = _telemetry_cache[index % len(_telemetry_cache)]
                payload = {
                    "video_time": item.get("video_time_sec", index),
                    "battery": item.get("battery", 80),
                    "signal": item.get("signal", 90),
                    "altitude": item.get("altitude", 15.0),
                    "speed": item.get("speed", 4.0),
                    "satellites": item.get("satellites", 24),
                    "mode": item.get("mode", "3D FIX"),
                }
                index += 1
            else:
                # 兜底 mock 数据
                payload = {
                    "video_time": index,
                    "battery": 80.0,
                    "signal": 92,
                    "altitude": 15.4,
                    "speed": 4.2,
                    "satellites": 24,
                    "mode": "3D FIX",
                }
                index += 1

            await websocket.send_json(payload)

    except WebSocketDisconnect:
        logger.info("Telemetry WebSocket disconnected")
    except Exception as e:
        logger.warning("Telemetry WebSocket error: %s", e)
