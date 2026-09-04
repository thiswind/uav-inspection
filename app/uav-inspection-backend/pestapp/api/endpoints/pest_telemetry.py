from fastapi import APIRouter, Query
from pestapp.schemas.pest import (
    TelemetryResponse,
    TelemetryData,
    PestStatisticsResponse,
    PestStatItem
)
from pestapp.services.pest_service import PestService
import random

router = APIRouter()

@router.get("/telemetry", response_model=TelemetryResponse, summary="获取无人机实时遥测数据(与视频同步)")
async def get_telemetry(video_time: int = Query(0, description="当前播放的视频秒数")):
    """
    前端视频播放器每到一秒，请求该接口，从 MongoDB 返回时间戳对齐的无人机姿态数据。
    """
    record = await PestService.get_live_telemetry(video_time_sec=video_time)

    return TelemetryResponse(
        code=200,
        message="success",
        data=TelemetryData(
            battery=record.get("battery", 0),
            signal=record.get("signal", 0),
            altitude=record.get("altitude", 0),
            speed=record.get("speed", 0),
            satellites=record.get("satellites", 0),
            mode=record.get("mode", "UNKNOWN")
        )
    )

@router.get("/statistics", response_model=PestStatisticsResponse, summary="获取病虫害分布统计")
async def get_statistics():
    return PestStatisticsResponse(
        code=200,
        message="success",
        data=[
            PestStatItem(name="茶尺蠖", value=random.randint(10, 20)),
            PestStatItem(name="叶片病斑", value=random.randint(2, 8)),
            PestStatItem(name="异物遮挡", value=random.randint(1, 5)),
        ]
    )
