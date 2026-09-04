from __future__ import annotations

import base64
from pathlib import Path
import time
from typing import Any

import cv2
import numpy as np
from deployment_paths import backend_path
from optional_inference import inference_device, load_yolo_model

MODEL_PATH = backend_path('powerapp', 'wire-pole-seg.pt')

CLASS_NAMES = {
    1: 'WirePole',
    2: 'Wire',
}

CLASS_CN = {
    1: '电杆',
    2: '线缆',
}

CLASS_COLORS = {
    'WirePole': (0, 255, 0),
    'Wire': (255, 255, 0),
}


class PowerDetector:
    _instance: 'PowerDetector | None' = None

    def __new__(cls) -> 'PowerDetector':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self.model: Any | None = None
        self.device = 'cpu'
        self.conf_threshold = 0.3
        self.iou_threshold = 0.45
        self._initialized = True

    def load_model(self) -> None:
        if self.model is not None:
            return
        self.model = load_yolo_model(MODEL_PATH)
        self.device = inference_device()
        try:
            self.model.fuse()
        except Exception:
            pass

    def detect(self, image_bgr: np.ndarray, conf_threshold: float | None = None, iou_threshold: float | None = None) -> dict[str, Any]:
        self.load_model()
        assert self.model is not None

        conf = self.conf_threshold if conf_threshold is None else conf_threshold
        iou = self.iou_threshold if iou_threshold is None else iou_threshold
        started_at = time.perf_counter()

        results = self.model(image_bgr, conf=conf, iou=iou, classes=[1, 2], verbose=False, device=self.device)
        detections: list[dict[str, Any]] = []
        stats = {'Wire': 0, 'WirePole': 0}
        annotated = image_bgr.copy()

        for result in results:
            boxes = result.boxes
            if boxes is None:
                continue
            for index in range(len(boxes)):
                cls_id = int(boxes.cls[index].item())
                if cls_id not in CLASS_NAMES:
                    continue
                score = float(boxes.conf[index].item())
                x1, y1, x2, y2 = [float(v) for v in boxes.xyxy[index].tolist()]
                label = CLASS_NAMES[cls_id]
                color = CLASS_COLORS[label]
                stats[label] += 1

                detections.append({
                    'class': cls_id,
                    'name': label,
                    'cn': CLASS_CN[cls_id],
                    'bbox': [round(x1, 1), round(y1, 1), round(x2, 1), round(y2, 1)],
                    'conf': round(score, 3),
                })

                self._draw_box(annotated, CLASS_CN[cls_id], score, (x1, y1, x2, y2), color)

        _, buffer = cv2.imencode('.jpg', annotated)
        annotated_base64 = base64.b64encode(buffer).decode('utf-8')
        inference_ms = round((time.perf_counter() - started_at) * 1000, 2)

        return {
            'detections': detections,
            'count': len(detections),
            'stats': stats,
            'annotated_image': annotated_base64,
            'inference_ms': inference_ms,
        }

    def detect_base64(self, image_base64: str, conf_threshold: float | None = None, iou_threshold: float | None = None) -> dict[str, Any]:
        image_bytes = base64.b64decode(image_base64)
        np_arr = np.frombuffer(image_bytes, np.uint8)
        image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError('Unable to decode image')
        return self.detect(image, conf_threshold=conf_threshold, iou_threshold=iou_threshold)

    def update_config(self, confidence: float | None = None, iou: float | None = None) -> dict[str, Any]:
        if confidence is not None:
            self.conf_threshold = max(0.05, min(0.95, float(confidence)))
        if iou is not None:
            self.iou_threshold = max(0.05, min(0.95, float(iou)))
        return {'confidence': self.conf_threshold, 'iou': self.iou_threshold}

    def get_info(self) -> dict[str, Any]:
        self.load_model()
        return {
            'system': {
                'cuda_available': self.device.startswith('cuda'),
                'device': self.device,
            },
            'model': {
                'name': MODEL_PATH.name,
                'classes': list(CLASS_CN.values()),
            },
            'config': {
                'confidence': self.conf_threshold,
                'iou': self.iou_threshold,
            },
            'capabilities': {
                'video_file': True,
                'single_frame_detection': True,
            },
        }

    @staticmethod
    def _draw_box(image: np.ndarray, label: str, score: float, bbox: tuple[float, float, float, float], color: tuple[int, int, int]) -> None:
        x1, y1, x2, y2 = [int(v) for v in bbox]
        cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)
        text = f'{label} {score:.2f}'
        font = cv2.FONT_HERSHEY_SIMPLEX
        text_size, _ = cv2.getTextSize(text, font, 0.6, 2)
        text_w, text_h = text_size
        cv2.rectangle(image, (x1, max(0, y1 - text_h - 10)), (x1 + text_w + 8, y1), color, -1)
        cv2.putText(image, text, (x1 + 4, y1 - 6), font, 0.6, (0, 0, 0), 2, cv2.LINE_AA)


power_detector = PowerDetector()
