import asyncio
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
# 注意：直接从 ai_inference 导入已经实例化好的 engine
from heatmapapp.services.ai_inference import engine 

router = APIRouter()
logger = logging.getLogger(__name__)

@router.websocket("/inference/{task_id}")
async def websocket_endpoint(websocket: WebSocket, task_id: str):
    await websocket.accept()
    logger.info("Inference WebSocket connected: %s", task_id)
    if not engine.start_processing(task_id):
        await websocket.send_json({"code": 503, "taskId": task_id, "error": engine.model_error})
        await websocket.close(code=1013, reason="Optional inference unavailable")
        return
    try:
        last_frame_id = -1
        last_alert_id = None
        while True:
            stats = engine.get_latest_stats(task_id)

            if stats.get("frameId", 0) != last_frame_id and stats.get("frameId", 0) > 0:
                payload = {
                    "taskId": task_id,
                    **stats,
                    "timestamp": "Live",
                    "isAlert": stats.get("totalCount", 0) >= engine.alert_threshold
                }

                alert = stats.get("alert")
                if alert and alert.get("id") != last_alert_id:
                    payload["alert"] = alert
                    last_alert_id = alert.get("id")

                await websocket.send_json(payload)
                last_frame_id = stats["frameId"]

            await asyncio.sleep(0.05)
            
    except WebSocketDisconnect:
        logger.info("Inference WebSocket disconnected: %s", task_id)
    except Exception as e:
        logger.warning("Inference WebSocket error: %s", e)

# ⚠️ 注意：文件末尾绝对不要再写 router = APIRouter() 了！
