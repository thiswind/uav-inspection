from fastapi import APIRouter, HTTPException
from pestapp.schemas.pest import (
    MissionCommandRequest,
    MissionCreateRequest,
    MissionDetailResponse,
    StandardResponse
)
from pestapp.services.pest_store import pest_store

router = APIRouter()

@router.post("/mission/control", response_model=StandardResponse, summary="发送任务与云台控制指令")
async def control_mission(req: MissionCommandRequest):
    return StandardResponse(
        code=200,
        message=f"Command '{req.command}' executed successfully",
        data={"status": "processing"}
    )

@router.post("/missions", response_model=MissionDetailResponse, summary="创建巡检任务")
async def create_mission(payload: MissionCreateRequest):
    mission = pest_store.create_mission(payload.dict())
    return MissionDetailResponse(code=200, message="success", data=mission)

@router.get("/missions/{mission_id}", response_model=MissionDetailResponse, summary="获取任务详情")
async def get_mission(mission_id: str):
    mission = pest_store.get_mission(mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail="Mission not found")
    return MissionDetailResponse(code=200, message="success", data=mission)

@router.post("/missions/{mission_id}/cancel", response_model=MissionDetailResponse, summary="取消任务")
async def cancel_mission(mission_id: str):
    mission = pest_store.cancel_mission(mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail="Mission not found")
    return MissionDetailResponse(code=200, message="success", data=mission)
