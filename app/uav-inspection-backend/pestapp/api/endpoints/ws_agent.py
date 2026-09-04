"""Agent 对话 WebSocket — 边缘智能协同决策"""
import json
import asyncio
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()
logger = logging.getLogger(__name__)

RESPONSES = [
    {"role": "agent", "content": "巡检系统已就位，当前算力节点：Jetson Orin Nano。", "type": "info"},
    {"role": "agent", "content": "【视觉异常告警】检测到疑似高危病害聚集。但当前视角下叶片遮挡率达 42%。建议调整云台俯仰角至 -60°。", "type": "warning"},
    {
        "role": "agent",
        "content": "已检索到 3 处异常点位：\\n1. A区茶尺蠖聚集 (置信度 98%)\\n2. B区叶片病斑 (置信度 85%)\\n3. C区异物遮挡 (置信度 72%)\\n建议优先处理 A 区。",
        "type": "action",
    },
    {"role": "agent", "content": "正在协同边缘计算节点调整策略，启动 Actor-Critic 决策网络...", "type": "info"},
]


@router.websocket("/agent/chat")
async def agent_chat(websocket: WebSocket):
    await websocket.accept()
    logger.info("Agent WebSocket connected")

    # 发送欢迎消息
    await websocket.send_json({"role": "agent", "content": "巡检系统已就位，当前算力节点：Jetson Orin Nano。", "type": "info"})

    response_index = 0
    try:
        while True:
            try:
                # 接收用户输入
                raw = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                message = json.loads(raw)
                user_content = message.get("content", "")
                role = message.get("role", "user")

                logger.info("Agent WebSocket received a message")

                # 模拟 Agent 思考 & 回复
                await asyncio.sleep(0.8)

                response = RESPONSES[response_index % len(RESPONSES)]
                response_index += 1
                await websocket.send_json(response)

            except asyncio.TimeoutError:
                # 心跳维持
                await websocket.send_json({"role": "system", "content": "ping", "type": "info"})

    except WebSocketDisconnect:
        logger.info("Agent WebSocket disconnected")
    except Exception as e:
        logger.warning("Agent WebSocket error: %s", e)
