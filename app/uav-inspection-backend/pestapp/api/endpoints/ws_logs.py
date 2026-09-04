"""系统日志流 WebSocket"""
import json
import asyncio
import logging
import time
import random
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()
logger = logging.getLogger(__name__)

# 预置的系统日志池（符合病虫害巡检业务语义）
LOG_POOL = [
    {"level": "INFO", "tag": "空间计算", "message": "正在解析 WGS84 坐标系数据..."},
    {"level": "WARNING", "tag": "视点决策", "message": "目标区域叶片遮挡度 > 30%，触发 Actor-Critic 决策网络。"},
    {"level": "INFO", "tag": "路径规划", "message": "航点 12/35 已通过，偏航误差 0.3°。"},
    {"level": "SUCCESS", "tag": "模型推理", "message": "ResNet-50 分类完成，病害类别：茶尺蠖 (置信度 0.96)。"},
    {"level": "INFO", "tag": "传感器融合", "message": "RTK GPS 已锁星 24 颗，精度 ±0.02m。"},
    {"level": "WARNING", "tag": "电池监控", "message": "电量 58%，建议 5 分钟后返航。"},
    {"level": "INFO", "tag": "强化学习", "message": "状态空间计算中：当前云台俯仰角 -45°..."},
    {"level": "ERROR", "tag": "图像传输", "message": "帧丢失率 > 5%，正在切换信道。"},
]


@router.websocket("/system/logs")
async def system_logs(websocket: WebSocket):
    await websocket.accept()
    logger.info("System logs WebSocket connected")

    # 先发送一批初始化日志
    init_logs = [
        {"time": _now(), "level": "INFO", "tag": "系统初始化", "message": "FastAPI 边缘网关连接成功。"},
        {"time": _now(), "level": "SUCCESS", "tag": "模型加载", "message": "YOLO 目标检测模型权重加载完毕。"},
    ]
    for log in init_logs:
        await websocket.send_json(log)

    try:
        while True:
            await asyncio.sleep(random.uniform(2.0, 5.0))
            log = random.choice(LOG_POOL)
            payload = {
                "time": _now(),
                "level": log["level"],
                "tag": log["tag"],
                "message": log["message"],
            }
            await websocket.send_json(payload)

    except WebSocketDisconnect:
        logger.info("System logs WebSocket disconnected")
    except Exception as e:
        logger.warning("System logs WebSocket error: %s", e)


def _now() -> str:
    return time.strftime("%H:%M:%S", time.localtime())
