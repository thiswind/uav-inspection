from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "UAV Inspection API"
    # MongoDB配置，开发阶段先用本地或者你在Docker中起的
    MONGO_URI: str = "mongodb://127.0.0.1:27017"
    DATABASE_NAME: str = "uav_inspection_db"
    
    # 视频存储的基础路径 (未来对接 MinIO 或 本地文件系统)
    VIDEO_STORAGE_BASE: str = "/videos/"

    class Config:
        env_file = ".env"

settings = Settings()