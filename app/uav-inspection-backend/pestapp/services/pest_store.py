import uuid
from datetime import datetime
from typing import Dict, List, Optional

class PestMockStore:
    def __init__(self) -> None:
        self._routes = [
            {
                "id": "route_a",
                "name": "A区茶园自主巡检航线",
                "waypoints": 35,
                "duration_min": 24,
                "area_mu": 20,
                "status": "running",
                "video_file": "pest-inspection1.mp4"
            },
            {
                "id": "route_b",
                "name": "B区烟草三维环绕航线",
                "waypoints": 12,
                "duration_min": 8,
                "area_mu": None,
                "status": "idle",
                "video_file": "pest-inspection2.MP4"
            }
        ]
        self._models = [
            {
                "id": "yolo_v8_edge",
                "name": "YOLO-v8 目标检测模型",
                "runtime": "edge",
                "status": "active",
                "description": "端侧推理模型"
            },
            {
                "id": "resnet_cloud",
                "name": "ResNet-50 病害分类大模型",
                "runtime": "cloud",
                "status": "standby",
                "description": "云端分类模型"
            }
        ]
        self._reports = [
            {
                "id": "rep_20260429_a",
                "title": "20260429_A区茶园病虫害评估报告",
                "generated_at": "2026-05-06T14:30:00+08:00",
                "format": "pdf",
                "attachment_count": 12,
                "file_name": "20260429_A区茶园病虫害评估报告.pdf"
            },
            {
                "id": "rep_20260427_b",
                "title": "20260427_B区烟草巡检日志",
                "generated_at": "2026-05-04T09:20:00+08:00",
                "format": "csv",
                "attachment_count": 0,
                "file_name": "20260427_B区烟草巡检日志.csv"
            }
        ]
        self._missions: Dict[str, Dict] = {}

    def list_routes(self) -> List[Dict]:
        return list(self._routes)

    def get_route(self, route_id: str) -> Optional[Dict]:
        return next((item for item in self._routes if item["id"] == route_id), None)

    def activate_route(self, route_id: str) -> Optional[Dict]:
        selected = None
        for route in self._routes:
            if route["id"] == route_id:
                route["status"] = "running"
                selected = route
            else:
                route["status"] = "idle"
        return selected

    def list_models(self) -> List[Dict]:
        return list(self._models)

    def activate_model(self, model_id: str) -> Optional[Dict]:
        selected = None
        for model in self._models:
            if model["id"] == model_id:
                model["status"] = "active"
                selected = model
            else:
                model["status"] = "standby"
        return selected

    def list_reports(self) -> List[Dict]:
        return list(self._reports)

    def get_report(self, report_id: str) -> Optional[Dict]:
        return next((item for item in self._reports if item["id"] == report_id), None)

    def create_mission(self, payload: Dict) -> Dict:
        mission_id = f"mis_{uuid.uuid4().hex[:8]}"
        created_at = datetime.now().isoformat()
        mission = {
            "id": mission_id,
            "name": payload.get("name") or f"巡检任务-{mission_id}",
            "status": "running",
            "route_id": payload["route_id"],
            "model_id": payload["model_id"],
            "created_at": created_at,
            "scheduled_at": payload.get("scheduled_at")
        }
        self._missions[mission_id] = mission
        return mission

    def get_mission(self, mission_id: str) -> Optional[Dict]:
        return self._missions.get(mission_id)

    def cancel_mission(self, mission_id: str) -> Optional[Dict]:
        mission = self._missions.get(mission_id)
        if mission:
            mission["status"] = "canceled"
        return mission

pest_store = PestMockStore()
