from pydantic import BaseModel
from typing import List, Optional

# ------------- 无人机遥测数据 -------------
class TelemetryData(BaseModel):
    battery: float
    signal: int
    altitude: float
    speed: float
    satellites: int
    mode: str

# ------------- 系统状态响应 -------------
class TelemetryResponse(BaseModel):
    code: int
    message: str
    data: TelemetryData

# ------------- 病害统计数据 -------------
class PestStatItem(BaseModel):
    name: str
    value: int

class PestStatisticsResponse(BaseModel):
    code: int
    message: str
    data: List[PestStatItem]

# ------------- 控制指令请求 -------------
class MissionCommandRequest(BaseModel):
    command: str  # e.g., "start", "stop", "return"
    params: dict = {}

class StandardResponse(BaseModel):
    code: int
    message: str
    data: dict = {}

# ------------- 航线 -------------
class RouteItem(BaseModel):
    id: str
    name: str
    waypoints: int
    duration_min: int
    area_mu: Optional[int] = None
    status: str = "idle"

class RouteListResponse(BaseModel):
    code: int
    message: str
    data: List[RouteItem]

class RouteDetailResponse(BaseModel):
    code: int
    message: str
    data: RouteItem

# ------------- 视觉模型 -------------
class VisionModelItem(BaseModel):
    id: str
    name: str
    runtime: str  # edge | cloud
    status: str = "standby"
    description: Optional[str] = None

class VisionModelListResponse(BaseModel):
    code: int
    message: str
    data: List[VisionModelItem]

class VisionModelDetailResponse(BaseModel):
    code: int
    message: str
    data: VisionModelItem

# ------------- 报告 -------------
class ReportItem(BaseModel):
    id: str
    title: str
    generated_at: str
    format: str  # pdf | csv
    attachment_count: Optional[int] = None
    size_bytes: Optional[int] = None
    file_name: Optional[str] = None

class ReportListResponse(BaseModel):
    code: int
    message: str
    data: List[ReportItem]

# ------------- 任务 -------------
class MissionCreateRequest(BaseModel):
    route_id: str
    model_id: str
    name: Optional[str] = None
    scheduled_at: Optional[str] = None
    params: dict = {}

class MissionDetail(BaseModel):
    id: str
    name: str
    status: str
    route_id: str
    model_id: str
    created_at: Optional[str] = None
    scheduled_at: Optional[str] = None

class MissionDetailResponse(BaseModel):
    code: int
    message: str
    data: MissionDetail