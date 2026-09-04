from fastapi import APIRouter, HTTPException
from pestapp.schemas.pest import VisionModelListResponse, VisionModelDetailResponse
from pestapp.services.pest_store import pest_store

router = APIRouter()

@router.get("/models", response_model=VisionModelListResponse, summary="获取视觉模型列表")
async def list_models():
    return VisionModelListResponse(code=200, message="success", data=pest_store.list_models())

@router.post("/models/{model_id}/activate", response_model=VisionModelDetailResponse, summary="激活指定模型")
async def activate_model(model_id: str):
    model = pest_store.activate_model(model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    return VisionModelDetailResponse(code=200, message="success", data=model)
