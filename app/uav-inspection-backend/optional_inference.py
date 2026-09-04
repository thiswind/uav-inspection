"""Load the optional AI runtime only when an inference operation needs it."""
from __future__ import annotations

from pathlib import Path
from typing import Any
from importlib.util import find_spec


class InferenceUnavailableError(FileNotFoundError):
    """An optional model/runtime is absent; existing API handlers return HTTP 503."""


def inference_dependencies_available() -> bool:
    try:
        return all(find_spec(name) is not None for name in ("torch", "ultralytics"))
    except (ImportError, ValueError):
        return False


def load_yolo_model(path: Path | str) -> Any:
    model_path = Path(path)
    if not model_path.is_file():
        raise InferenceUnavailableError(
            f"未安装可选模型 {model_path.name}。请将 02-data 数据包放到 01-app 旁边，"
            "或设置 UAV_DATA_DIR；页面浏览和文件上传不受影响。"
        )
    try:
        from ultralytics import YOLO
    except Exception as exc:
        raise InferenceUnavailableError(
            "AI 推理依赖未安装或不可用。请安装 requirements-inference.txt，"
            "然后重新启动服务；页面浏览和文件上传不受影响。"
        ) from exc
    try:
        return YOLO(str(model_path))
    except Exception as exc:
        raise InferenceUnavailableError(
            f"可选模型 {model_path.name} 无法加载，请检查数据包和 AI 推理依赖：{exc}"
        ) from exc


def inference_device() -> str:
    try:
        import torch
        return "cuda:0" if torch.cuda.is_available() else "cpu"
    except Exception:
        return "cpu"
