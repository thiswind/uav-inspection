"""热力客流监测系统配置"""
from pydantic_settings import BaseSettings
from deployment_paths import backend_path


class Settings(BaseSettings):
    PROJECT_NAME: str = "玫瑰园无人机巡检系统"
    VIDEO_STORAGE_DIR: str = str(backend_path("heatmapdata", "videos"))
    SNAPSHOT_STORAGE_DIR: str = str(backend_path("heatmapdata", "snapshots"))
    MODEL_WEIGHT_PATH: str = str(backend_path("heatmapweight", "renliu.pt"))

    # AI 推理参数
    YOLO_CONFIDENCE_THRESHOLD: float = 0.25
    ALERT_THRESHOLD: int = 10
    ALERT_COOLDOWN_SEC: int = 5
    HFOV_DEG: float = 80.0

    # 默认参考坐标 (玫瑰园)
    DEFAULT_LAT: float = 30.5594
    DEFAULT_LON: float = 104.0657

    class Config:
        env_file = ".env"


settings = Settings()
