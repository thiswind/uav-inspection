from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from deployment_paths import backend_path
from optional_inference import inference_device, load_yolo_model

CLASS_NAMES = {0: "rose", 1: "picked", 2: "bud"}
CLASS_CN = {0: "盛开花", 1: "已采摘", 2: "花苞"}


def _model_candidates() -> list[Path]:
    env_path = os.getenv("ROSE_MODEL_PATH")
    candidates = []
    if env_path:
        candidates.append(Path(env_path).expanduser())

    candidates.extend(
        [
            backend_path("roseapp", "rose-detect-best.pt"),
            backend_path("roseapp", "best.pt"),
        ]
    )
    return candidates


def _resolve_model_path() -> Path:
    for candidate in _model_candidates():
        if candidate.exists():
            return candidate
    return _model_candidates()[0]


class RoseDetector:
    _instance: "RoseDetector | None" = None

    def __new__(cls) -> "RoseDetector":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self.model: Any | None = None
        self.device = "cpu"
        self.conf_threshold = 0.6
        self.iou_threshold = 0.45
        self._model_path: Path | None = None
        self._initialized = True

    def load_model(self) -> None:
        if self.model is not None:
            return

        model_path = _resolve_model_path()
        self.model = load_yolo_model(model_path)
        self.device = inference_device()
        self._model_path = model_path
        try:
            self.model.fuse()
        except Exception:
            pass

    def detect(
        self,
        image_bgr: np.ndarray,
        conf_threshold: float | None = None,
        iou_threshold: float | None = None,
    ) -> dict[str, Any]:
        self.load_model()
        assert self.model is not None

        conf = self.conf_threshold if conf_threshold is None else conf_threshold
        iou = self.iou_threshold if iou_threshold is None else iou_threshold
        results = self.model(image_bgr, conf=conf, iou=iou, verbose=False, device=self.device)

        detections: list[dict[str, Any]] = []
        class_counts = {"rose": 0, "picked": 0, "bud": 0}

        for result in results:
            boxes = result.boxes
            if boxes is None:
                continue
            for index in range(len(boxes)):
                cls_id = int(boxes.cls[index].item())
                cls_name = CLASS_NAMES.get(cls_id)
                if cls_name is None:
                    continue

                score = float(boxes.conf[index].item())
                x1, y1, x2, y2 = [float(v) for v in boxes.xyxy[index].tolist()]

                detections.append(
                    {
                        "class": cls_id,
                        "name": cls_name,
                        "cn": CLASS_CN.get(cls_id, "未知"),
                        "bbox": [round(x1, 1), round(y1, 1), round(x2, 1), round(y2, 1)],
                        "conf": round(score, 3),
                    }
                )
                class_counts[cls_name] += 1

        return {
            "detections": detections,
            "count": len(detections),
            "class_counts": class_counts,
        }

    def detect_base64(
        self,
        b64_image: str,
        conf_threshold: float | None = None,
        iou_threshold: float | None = None,
    ) -> dict[str, Any]:
        image_bytes = base64.b64decode(b64_image)
        image_array = np.frombuffer(image_bytes, np.uint8)
        image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("无法解码图片")
        return self.detect(image, conf_threshold=conf_threshold, iou_threshold=iou_threshold)

    def get_info(self) -> dict[str, Any]:
        model_path = self._model_path or _resolve_model_path()
        return {
            "device": self.device,
            "model_loaded": self.model is not None,
            "model_path": str(model_path),
            "cuda_available": self.device.startswith("cuda"),
            "config": {
                "confidence": self.conf_threshold,
                "iou": self.iou_threshold,
            },
        }


rose_detector = RoseDetector()
