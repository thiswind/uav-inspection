from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from pestapp.api.endpoints import pest
from pestapp.api.endpoints import ws_agent, ws_logs, ws_telemetry
from pestapp.core.database import connect_to_mongo, close_mongo_connection
from pestapp.services.pest_service import PestService

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. 启动服务时，建立 MongoDB 连接
    await connect_to_mongo()
    # 2. 读取你现在的 JSON 文件（如果有的话），将其存入 Mongo，实现完美过渡
    await PestService.import_json_to_mongo("mock_track.json")
    yield
    # 3. 关闭服务时，断开连接
    await close_mongo_connection()

app = FastAPI(title="UAV Inspection API", version="1.0.0", lifespan=lifespan)

# 配置跨域请求（CORS），允许前端（Vue）访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境请修改为前端的真实域名/端口
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册 REST API 路由模块
app.include_router(pest.router, prefix="/api/v1/pest", tags=["病虫害巡检"])

# 注册 WebSocket 路由模块
app.include_router(ws_agent.router, prefix="/ws/v1", tags=["Agent对话"])
app.include_router(ws_logs.router, prefix="/ws/v1", tags=["系统日志"])
app.include_router(ws_telemetry.router, prefix="/ws/v1", tags=["遥测数据流"])

@app.get("/")
async def root():
    return {"message": "Welcome to UAV Inspection Backend API. Go to /docs for Swagger UI"}