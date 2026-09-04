from fastapi import APIRouter, HTTPException
from pestapp.schemas.pest import RouteListResponse, RouteDetailResponse
from pestapp.services.pest_store import pest_store

router = APIRouter()

@router.get("/routes", response_model=RouteListResponse, summary="获取巡检航线列表")
async def list_routes():
    return RouteListResponse(code=200, message="success", data=pest_store.list_routes())

@router.post("/routes/{route_id}/activate", response_model=RouteDetailResponse, summary="激活指定航线")
async def activate_route(route_id: str):
    route = pest_store.activate_route(route_id)
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")
    return RouteDetailResponse(code=200, message="success", data=route)
