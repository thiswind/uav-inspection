import json
import os
from typing import List, Dict, Any
from pestapp.core.database import db_manager
from deployment_paths import backend_path

class PestService:
    _mock_telemetry_by_time: Dict[int, Dict[str, Any]] = {}

    @staticmethod
    def _get_base_data_dir() -> str:
        return str(backend_path("pestdata"))

    @classmethod
    def _load_mock_track(cls, json_file_name: str) -> None:
        if cls._mock_telemetry_by_time:
            return

        file_path = os.path.join(cls._get_base_data_dir(), json_file_name)
        if not os.path.exists(file_path):
            return

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    cls._mock_telemetry_by_time = {
                        int(item.get("video_time_sec", -1)): item
                        for item in data
                        if isinstance(item, dict) and "video_time_sec" in item
                    }
        except Exception:
            cls._mock_telemetry_by_time = {}

    @staticmethod
    async def import_json_to_mongo(json_file_name: str) -> None:
        """
        桥接方案：将你现在的 track.json 文件读取并录入 MongoDB。
        这在系统刚启动并发现数据库为空时自动执行，方便你过渡。
        """
        try:
            if db_manager.db is None:
                return
            collection = db_manager.db["telemetry_tracks"]
            # 检查集合是否已有数据，如果没有则导入
            count = await collection.count_documents({})
            if count == 0:
                file_path = os.path.join(PestService._get_base_data_dir(), json_file_name)
                
                if os.path.exists(file_path):
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if isinstance(data, list) and len(data) > 0:
                            await collection.insert_many(data)
                            print(f"成功将 {len(data)} 条轨迹与AI识别结果从 {json_file_name} 导入 MongoDB！")
        except Exception as e:
            print(f"MongoDB 导入失败 (未运行MongoDB环境?): {e}")

    @staticmethod
    async def get_live_telemetry(video_time_sec: int) -> Dict[str, Any]:
        """
        根据视频播放进度(当前秒数)，去 MongoDB 中查那对应那一秒的无人机姿态和AI识别数据
        """
        try:
            collection = db_manager.db["telemetry_tracks"]
            # 找到对应视频时间那一秒的数据
            record = await collection.find_one({"video_time_sec": video_time_sec}, {"_id": 0})
            if record:
                return record
        except:
            pass

        PestService._load_mock_track("mock_track.json")
        record = PestService._mock_telemetry_by_time.get(video_time_sec)
        if record:
            return record

        # 降级：如果未连上 MongoDB 或未匹配到轨迹数据，这里给个兜底返回防止前端出错
        return {
            "battery": 80.0,
            "signal": 90,
            "altitude": 15.0,
            "speed": 4.0,
            "satellites": 24,
            "mode": "MOCK_DB_FAIL",
        }
