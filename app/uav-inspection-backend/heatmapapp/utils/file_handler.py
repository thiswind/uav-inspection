import asyncio
from typing import Dict, Any, Optional
from datetime import datetime

# 定义任务状态常量
class TaskStatus:
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class TaskManager:
    def __init__(self):
        # 存储内存中的活跃任务状态
        self._tasks: Dict[str, Dict[str, Any]] = {}

    def create_task(self, task_id: str, task_name: str) -> Dict[str, Any]:
        """
        创建一个新任务记录
        """
        task_info = {
            "taskId": task_id,
            "taskName": task_name,
            "status": TaskStatus.PENDING,
            "progress": 0,
            "uploadTime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "startTime": None,
            "endTime": None,
            "error": None
        }
        self._tasks[task_id] = task_info
        return task_info

    def update_status(self, task_id: str, status: str, progress: int = None, error: str = None):
        """
        更新任务状态和进度
        """
        if task_id in self._tasks:
            self._tasks[task_id]["status"] = status
            if progress is not None:
                self._tasks[task_id]["progress"] = progress
            if error:
                self._tasks[task_id]["error"] = error
            
            if status == TaskStatus.PROCESSING and not self._tasks[task_id]["startTime"]:
                self._tasks[task_id]["startTime"] = datetime.now().isoformat()
            if status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                self._tasks[task_id]["endTime"] = datetime.now().isoformat()

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        获取单个任务详情
        """
        return self._tasks.get(task_id)

    def get_all_active_tasks(self):
        """
        获取所有正在进行中的任务
        """
        return [t for t in self._tasks.values() if t["status"] == TaskStatus.PROCESSING]

# 全局单例，确保整个后端共用同一个管理器
task_manager = TaskManager()