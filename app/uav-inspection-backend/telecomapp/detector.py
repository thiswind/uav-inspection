from __future__ import annotations

import base64
from pathlib import Path
import time
from typing import Any

import cv2
import numpy as np
from deployment_paths import backend_path
from optional_inference import load_yolo_model

MODEL_PATH = backend_path('telecomapp', 'station2-best.pt')

CLASS_NAMES = {
    3: 'Station',
    4: 'Antenna',
}

CLASS_CN = {
    3: '基站',
    4: '天线',
}

CLASS_COLORS = {
    'Station': (0, 255, 0),
    'Antenna': (0, 165, 255),
}


class TelecomDetector:
    _instance: 'TelecomDetector | None' = None

    def __new__(cls) -> 'TelecomDetector':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self.model: Any | None = None
        self.conf_threshold = 0.35
        self.iou_threshold = 0.45
        self._initialized = True

    def load_model(self) -> None:
        if self.model is not None:
            return
        self.model = load_yolo_model(MODEL_PATH)
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

        results = self.model(image_bgr, conf=conf, iou=iou, classes=[3, 4], verbose=False)
        detections: list[dict[str, Any]] = []
        stats = {'Station': 0, 'Antenna': 0}
        annotated = image_bgr.copy()

        for result in results:
            boxes = result.boxes
            if boxes is None:
                continue
            for index in range(len(boxes)):
                cls_id = int(boxes.cls[index].item())
                if cls_id not in CLASS_NAMES:
                    continue
                conf = float(boxes.conf[index].item())
                x1, y1, x2, y2 = [float(v) for v in boxes.xyxy[index].tolist()]
                label = CLASS_NAMES[cls_id]
                color = CLASS_COLORS[label]
                stats[label] += 1

                detections.append({
                    'class': cls_id,
                    'name': label,
                    'cn': CLASS_CN[cls_id],
                    'bbox': [round(x1, 1), round(y1, 1), round(x2, 1), round(y2, 1)],
                    'conf': round(conf, 3),
                })

                self._draw_box(annotated, label, conf, (x1, y1, x2, y2), color)

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
        return {
            'confidence': self.conf_threshold,
            'iou': self.iou_threshold,
        }

    def get_info(self) -> dict[str, Any]:
        self.load_model()
        return {
            'system': {
                'cuda_available': bool(getattr(getattr(self.model, 'predictor', None), 'device', None) and 'cuda' in str(self.model.predictor.device).lower()),
                'device': str(getattr(getattr(self.model, 'predictor', None), 'device', 'cpu')),
            },
            'model': {
                'name': 'station2-best.pt',
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
    def _draw_box(image: np.ndarray, label: str, conf: float, bbox: tuple[float, float, float, float], color: tuple[int, int, int]) -> None:
        x1, y1, x2, y2 = [int(v) for v in bbox]
        cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)
        text = f'{label}: {conf:.2f}'
        font = cv2.FONT_HERSHEY_SIMPLEX
        text_size, _ = cv2.getTextSize(text, font, 0.6, 2)
        text_w, text_h = text_size
        cv2.rectangle(image, (x1, max(0, y1 - text_h - 10)), (x1 + text_w + 8, y1), color, -1)
        cv2.putText(image, text, (x1 + 4, y1 - 6), font, 0.6, (255, 255, 255), 2, cv2.LINE_AA)


telecom_detector = TelecomDetector()
