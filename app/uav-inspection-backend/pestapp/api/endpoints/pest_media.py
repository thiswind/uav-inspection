import os
from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Query
from fastapi.responses import FileResponse, StreamingResponse
from pestapp.schemas.pest import StandardResponse
from pestapp.services.pest_media_service import iter_mjpeg_frames, push_frame, resolve_video_path

router = APIRouter()

@router.get("/video", summary="获取病虫害巡检视频文件")
@router.get("/vedio", summary="获取病虫害巡检视频文件")
async def get_video_stream(route_id: str | None = Query(default=None)):
    file_path = resolve_video_path(route_id)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Video file not found")

    return FileResponse(file_path, media_type="video/mp4", filename=os.path.basename(file_path))

@router.get("/video/frames", summary="获取病虫害巡检视频帧流(MJPEG)")
async def get_video_frames(route_id: str | None = Query(default=None)):
    return StreamingResponse(
        iter_mjpeg_frames(route_id=route_id),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )

@router.post("/video/push", response_model=StandardResponse, summary="推送病虫害巡检视频帧(JPEG)")
async def push_video_frame(request: Request, frame: UploadFile | None = File(default=None)):
    if frame is not None:
        payload = await frame.read()
    else:
        payload = await request.body()

    if not payload:
        raise HTTPException(status_code=400, detail="Frame payload is empty")

    if payload[:2] != b"\xff\xd8":
        raise HTTPException(status_code=415, detail="Only JPEG frames are supported")

    push_frame(payload)
    return StandardResponse(code=200, message="success", data={"size": len(payload)})
