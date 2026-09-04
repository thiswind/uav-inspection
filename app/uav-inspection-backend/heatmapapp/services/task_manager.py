import asyncio
from typing import Dict, Any, Optional
from datetime import datetime


class TaskStatus:
	PENDING = "PENDING"
	PROCESSING = "PROCESSING"
	COMPLETED = "COMPLETED"
	FAILED = "FAILED"


class TaskManager:
	def __init__(self):
		self._tasks: Dict[str, Dict[str, Any]] = {}

	def create_task(self, task_id: str, task_name: str) -> Dict[str, Any]:
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
		return self._tasks.get(task_id)

	def rename_task(self, task_id: str, task_name: str) -> None:
		if task_id in self._tasks:
			self._tasks[task_id]["taskName"] = task_name

	def delete_task(self, task_id: str) -> None:
		self._tasks.pop(task_id, None)

	def get_all_active_tasks(self):
		return [t for t in self._tasks.values() if t["status"] == TaskStatus.PROCESSING]


task_manager = TaskManager()
