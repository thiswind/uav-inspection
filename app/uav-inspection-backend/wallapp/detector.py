from __future__ import annotations

import base64
import math
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from deployment_paths import backend_path
from optional_inference import inference_device, load_yolo_model


MODEL_PATH = backend_path("wallapp", "wall-damage-best.pt")
LABEL_FONT_PATH = Path(r"C:\Windows\Fonts\msyhbd.ttc")
LABEL_FONT = ImageFont.truetype(str(LABEL_FONT_PATH), 18) if LABEL_FONT_PATH.exists() else ImageFont.load_default()
MIN_OBVIOUS_CONFIDENCE = 0.18
MODEL_IMGSZ = 1280
TARGET_CLASS_ID = 2
MODEL_CLASS_MIN_AREA_RATIO = {
    0: 0.00004,
    1: 0.0005,
    2: 0.00015,
    3: 0.0005,
}
MIN_OBVIOUS_AREA_RATIO = 0.018

CLASS_DEFS = {
    0: {"name": "Crack", "cn": "裂缝", "color": (68, 68, 239)},
    1: {"name": "Seepage", "cn": "渗水", "color": (166, 185, 20)},
    2: {"name": "TileSpalling", "cn": "面砖脱落/外墙破损", "color": (11, 132, 245)},
    3: {"name": "Hollowing", "cn": "空鼓风险", "color": (196, 113, 139)},
}

MODEL_CLASS_ALIASES = {
    "crack": 0,
    "seepage": 1,
    "water_stain": 1,
    "water_damage": 1,
    "tile_spalling": 2,
    "tilespalling": 2,
    "spalling": 2,
    "wall_damage": 2,
    "facade_damage": 2,
    "damage": 2,
}


def _empty_stats() -> dict[str, int]:
    return {item["name"]: 0 for item in CLASS_DEFS.values()}


class WallDetector:
    _instance: "WallDetector | None" = None

    def __new__(cls) -> "WallDetector":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self.model: Any | None = None
        self.model_error: str | None = None
        self.device = "cpu"
        self.conf_threshold = 0.30
        self.iou_threshold = 0.45
        self._initialized = True

    def load_model(self) -> None:
        if self.model is not None or self.model_error is not None:
            return
        try:
            self.model = load_yolo_model(MODEL_PATH)
            self.device = inference_device()
            try:
                self.model.fuse()
            except Exception:
                pass
        except Exception as exc:
            self.model_error = str(exc)
            self.model = None

    def is_model_available(self) -> bool:
        return MODEL_PATH.exists()

    def detect(
        self,
        image_bgr: np.ndarray,
        conf_threshold: float | None = None,
        iou_threshold: float | None = None,
    ) -> dict[str, Any]:
        self.load_model()
        if self.model is not None:
            try:
                return self._detect_with_model(image_bgr, conf_threshold, iou_threshold)
            except Exception as exc:
                self.model_error = str(exc)
        return self._detect_with_rules(image_bgr, conf_threshold, iou_threshold)

    def _detect_with_model(
        self,
        image_bgr: np.ndarray,
        conf_threshold: float | None,
        iou_threshold: float | None,
    ) -> dict[str, Any]:
        assert self.model is not None
        conf = max(MIN_OBVIOUS_CONFIDENCE, self.conf_threshold if conf_threshold is None else float(conf_threshold))
        iou = self.iou_threshold if iou_threshold is None else float(iou_threshold)
        started_at = time.perf_counter()
        height, width = image_bgr.shape[:2]

        results = self.model(image_bgr, conf=conf, iou=iou, imgsz=MODEL_IMGSZ, verbose=False, device=self.device)
        stats = _empty_stats()
        detections: list[dict[str, Any]] = []
        annotated = image_bgr.copy()

        for result in results:
            boxes = result.boxes
            if boxes is None:
                continue
            names = getattr(result, "names", getattr(self.model, "names", {})) or {}
            for index in range(len(boxes)):
                model_class = int(boxes.cls[index].item())
                class_id = self._canonical_class_id(model_class, names)
                if class_id not in CLASS_DEFS:
                    continue
                score = float(boxes.conf[index].item())
                x1, y1, x2, y2 = [float(v) for v in boxes.xyxy[index].tolist()]
                if not self._is_obvious_target(class_id, (x1, y1, x2, y2), width, height):
                    continue
                detection = self._make_detection(class_id, (x1, y1, x2, y2), score)
                detections.append(detection)
                stats[detection["name"]] += 1
                class_info = CLASS_DEFS[class_id]
                self._draw_box(annotated, class_info["cn"], score, detection["bbox"], class_info["color"])

        _, buffer = cv2.imencode(".jpg", annotated)
        annotated_base64 = base64.b64encode(buffer).decode("utf-8")
        inference_ms = round((time.perf_counter() - started_at) * 1000, 2)
        return {
            "detections": detections[:20],
            "count": len(detections[:20]),
            "stats": stats,
            "annotated_image": annotated_base64,
            "inference_ms": inference_ms,
            "image_size": {"width": width, "height": height},
            "model_mode": "yolo",
        }

    def _detect_with_rules(
        self,
        image_bgr: np.ndarray,
        conf_threshold: float | None,
        iou_threshold: float | None,
    ) -> dict[str, Any]:
        conf = max(MIN_OBVIOUS_CONFIDENCE, self.conf_threshold if conf_threshold is None else float(conf_threshold))
        iou = self.iou_threshold if iou_threshold is None else float(iou_threshold)
        started_at = time.perf_counter()

        height, width = image_bgr.shape[:2]
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)
        detections = self._collect_candidates(image_bgr, gray, hsv)
        detections = self._nms([item for item in detections if item["conf"] >= conf], iou)
        detections = detections[:8]
        stats = _empty_stats()
        annotated = image_bgr.copy()
        for item in detections:
            stats[item["name"]] += 1
            class_info = CLASS_DEFS[item["class"]]
            self._draw_box(annotated, class_info["cn"], item["conf"], item["bbox"], class_info["color"])

        _, buffer = cv2.imencode(".jpg", annotated)
        annotated_base64 = base64.b64encode(buffer).decode("utf-8")
        inference_ms = round((time.perf_counter() - started_at) * 1000, 2)

        return {
            "detections": detections,
            "count": len(detections),
            "stats": stats,
            "annotated_image": annotated_base64,
            "inference_ms": inference_ms,
            "image_size": {"width": width, "height": height},
            "model_mode": "rule_fallback",
        }

    def detect_base64(
        self,
        image_base64: str,
        conf_threshold: float | None = None,
        iou_threshold: float | None = None,
    ) -> dict[str, Any]:
        payload = image_base64.split(",", 1)[-1]
        image_bytes = base64.b64decode(payload)
        np_arr = np.frombuffer(image_bytes, np.uint8)
        image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("Unable to decode image")
        return self.detect(image, conf_threshold=conf_threshold, iou_threshold=iou_threshold)

    def update_config(self, confidence: float | None = None, iou: float | None = None) -> dict[str, Any]:
        if confidence is not None:
            self.conf_threshold = max(MIN_OBVIOUS_CONFIDENCE, min(0.95, float(confidence)))
        if iou is not None:
            self.iou_threshold = max(0.05, min(0.95, float(iou)))
        return {"confidence": self.conf_threshold, "iou": self.iou_threshold}

    def normalize_log_image(self, image_bytes: bytes, detections: list[dict[str, Any]]) -> bytes:
        image = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("Unable to decode log image")

        for detection in detections[:20]:
            class_id = int(detection.get("class", 2))
            class_info = CLASS_DEFS.get(class_id, CLASS_DEFS[2])
            bbox = [float(value) for value in detection.get("bbox", [])]
            if len(bbox) != 4:
                continue
            score = float(detection.get("conf", 0))
            x1, y1, _, _ = [int(value) for value in bbox]
            legacy_text = f"{class_info['cn']} {score:.2f}"
            legacy_size, _ = cv2.getTextSize(legacy_text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
            current_bbox = LABEL_FONT.getbbox(legacy_text)
            current_width = current_bbox[2] - current_bbox[0] + 10
            current_height = current_bbox[3] - current_bbox[1] + 10
            legacy_width = legacy_size[0] + 8
            legacy_height = legacy_size[1] + 10
            clear_top = max(0, y1 - max(current_height, legacy_height))
            clear_right = min(image.shape[1], x1 + max(current_width, legacy_width))
            cv2.rectangle(image, (x1, clear_top), (clear_right, y1), class_info["color"], -1)
            self._draw_box(image, class_info["cn"], score, bbox, class_info["color"])

        encoded, buffer = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
        if not encoded:
            raise ValueError("Unable to encode log image")
        return buffer.tobytes()

    def get_info(self) -> dict[str, Any]:
        self.load_model()
        cuda_available = self.device.startswith("cuda")
        model_loaded = self.model is not None
        model_name = MODEL_PATH.name if self.is_model_available() else "facade-rule-detector"
        return {
            "system": {
                "cuda_available": cuda_available,
                "device": self.device if model_loaded else f"{self.device} / rule-fallback",
            },
            "model": {
                "name": model_name,
                "available": self.is_model_available(),
                "loaded": model_loaded,
                "error": self.model_error,
                "classes": [item["cn"] for item in CLASS_DEFS.values()],
            },
            "config": {
                "confidence": self.conf_threshold,
                "iou": self.iou_threshold,
            },
            "capabilities": {
                "video_file": True,
                "single_frame_detection": True,
                "yolo_model": model_loaded,
                "rule_fallback": True,
            },
        }

    def _canonical_class_id(self, model_class: int, names: dict[int, str] | dict[str, str]) -> int:
        if isinstance(names, dict) and len(names) == 1:
            return 2
        label = str(names.get(model_class, "")) if isinstance(names, dict) else ""
        normalized = label.replace("-", "_").replace(" ", "_").lower()
        if normalized in MODEL_CLASS_ALIASES:
            return MODEL_CLASS_ALIASES[normalized]
        return model_class if model_class in CLASS_DEFS else 2

    def _collect_candidates(self, image_bgr: np.ndarray, gray: np.ndarray, hsv: np.ndarray) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []
        candidates.extend(self._detect_spalling(image_bgr, gray, hsv))
        candidates.sort(key=lambda item: item["conf"], reverse=True)
        return candidates

    def _detect_cracks(self, gray: np.ndarray) -> list[dict[str, Any]]:
        height, width = gray.shape[:2]
        blur = cv2.GaussianBlur(gray, (3, 3), 0)
        edges = cv2.Canny(blur, 55, 145)
        min_line = max(28, min(width, height) // 8)
        lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=42, minLineLength=min_line, maxLineGap=10)
        if lines is None:
            return []

        detections = []
        for line in lines[:80]:
            x1, y1, x2, y2 = [int(v) for v in line[0]]
            length = math.hypot(x2 - x1, y2 - y1)
            if length < min_line:
                continue
            margin = max(8, int(length * 0.05))
            bbox = self._clamp_bbox((x1 - margin, y1 - margin, x2 + margin, y2 + margin), width, height)
            aspect = abs(x2 - x1) / max(1, abs(y2 - y1))
            confidence = min(0.88, 0.44 + length / max(width, height) * 0.32 + min(aspect, 3) * 0.02)
            detections.append(self._make_detection(0, bbox, confidence))
        return detections[:3]

    def _detect_seepage(self, gray: np.ndarray, hsv: np.ndarray) -> list[dict[str, Any]]:
        height, width = gray.shape[:2]
        saturation = hsv[:, :, 1]
        value = hsv[:, :, 2]
        dark_limit = np.percentile(gray, 38)
        mask = ((gray < dark_limit) & (saturation < 95) & (value < 185)).astype(np.uint8) * 255
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 17))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        detections = []
        frame_area = width * height
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            area = w * h
            if area < frame_area * 0.006 or h < height * 0.08:
                continue
            ratio = h / max(1, w)
            confidence = min(0.86, 0.48 + min(area / frame_area, 0.08) * 3.1 + min(ratio, 3.0) * 0.04)
            detections.append(self._make_detection(1, (x, y, x + w, y + h), confidence))
        detections.sort(key=lambda item: item["conf"], reverse=True)
        return detections[:2]

    def _detect_spalling(self, image_bgr: np.ndarray, gray: np.ndarray, hsv: np.ndarray) -> list[dict[str, Any]]:
        height, width = gray.shape[:2]
        saturation = hsv[:, :, 1]
        value = hsv[:, :, 2]
        laplacian = cv2.convertScaleAbs(cv2.Laplacian(gray, cv2.CV_16S, ksize=3))
        high_texture = laplacian > np.percentile(laplacian, 82)
        bright_patch = value > np.percentile(value, 72)
        low_saturation = saturation < 120
        mask = (high_texture & bright_patch & low_saturation).astype(np.uint8) * 255
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (11, 11))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        detections = []
        frame_area = width * height
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            area = w * h
            if area < frame_area * MIN_OBVIOUS_AREA_RATIO or area > frame_area * 0.24:
                continue
            confidence = min(0.84, 0.46 + min(area / frame_area, 0.06) * 2.7)
            detections.append(self._make_detection(2, (x, y, x + w, y + h), confidence))
        detections.sort(key=lambda item: item["conf"], reverse=True)
        return detections[:2]

    def _detect_hollowing(self, gray: np.ndarray) -> list[dict[str, Any]]:
        height, width = gray.shape[:2]
        small = cv2.resize(gray, (max(8, width // 8), max(8, height // 8)))
        mean = cv2.blur(small.astype(np.float32), (5, 5))
        diff = cv2.absdiff(small.astype(np.float32), mean)
        _, _, _, max_loc = cv2.minMaxLoc(diff)
        x = int(max_loc[0] * 8)
        y = int(max_loc[1] * 8)
        box_w = max(56, width // 5)
        box_h = max(56, height // 5)
        bbox = self._clamp_bbox((x - box_w // 2, y - box_h // 2, x + box_w // 2, y + box_h // 2), width, height)
        texture_score = float(
            np.std(gray[max(0, bbox[1]) : max(bbox[1] + 1, bbox[3]), max(0, bbox[0]) : max(bbox[0] + 1, bbox[2])])
        )
        confidence = min(0.72, 0.42 + texture_score / 255 * 0.8)
        return [self._make_detection(3, bbox, confidence)] if confidence >= 0.5 else []

    def _fallback_detection(self, gray: np.ndarray) -> dict[str, Any]:
        height, width = gray.shape[:2]
        grad_x = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
        grad_y = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
        energy = cv2.magnitude(grad_x, grad_y)
        _, _, _, max_loc = cv2.minMaxLoc(cv2.GaussianBlur(energy, (21, 21), 0))
        box_w = max(64, width // 4)
        box_h = max(64, height // 4)
        x, y = max_loc
        bbox = self._clamp_bbox((x - box_w // 2, y - box_h // 2, x + box_w // 2, y + box_h // 2), width, height)
        return self._make_detection(TARGET_CLASS_ID, bbox, 0.58)

    @staticmethod
    def _has_visual_signal(gray: np.ndarray) -> bool:
        return float(np.std(gray)) > 4.0

    @staticmethod
    def _is_obvious_target(class_id: int, bbox: tuple[float, float, float, float], width: int, height: int) -> bool:
        x1, y1, x2, y2 = bbox
        area_ratio = max(0.0, x2 - x1) * max(0.0, y2 - y1) / max(1, width * height)
        return area_ratio >= MODEL_CLASS_MIN_AREA_RATIO.get(class_id, 0.0005)

    @staticmethod
    def _make_detection(
        class_id: int,
        bbox: tuple[float, float, float, float],
        confidence: float,
    ) -> dict[str, Any]:
        class_info = CLASS_DEFS[class_id]
        return {
            "class": class_id,
            "name": class_info["name"],
            "cn": class_info["cn"],
            "bbox": [round(float(v), 1) for v in bbox],
            "conf": round(float(confidence), 3),
        }

    @staticmethod
    def _clamp_bbox(bbox: tuple[int, int, int, int], width: int, height: int) -> tuple[int, int, int, int]:
        x1, y1, x2, y2 = bbox
        left = max(0, min(width - 2, min(x1, x2)))
        top = max(0, min(height - 2, min(y1, y2)))
        right = max(left + 1, min(width - 1, max(x1, x2)))
        bottom = max(top + 1, min(height - 1, max(y1, y2)))
        return left, top, right, bottom

    @staticmethod
    def _iou(box_a: list[float], box_b: list[float]) -> float:
        ax1, ay1, ax2, ay2 = box_a
        bx1, by1, bx2, by2 = box_b
        inter_x1 = max(ax1, bx1)
        inter_y1 = max(ay1, by1)
        inter_x2 = min(ax2, bx2)
        inter_y2 = min(ay2, by2)
        inter_w = max(0.0, inter_x2 - inter_x1)
        inter_h = max(0.0, inter_y2 - inter_y1)
        inter_area = inter_w * inter_h
        area_a = max(1.0, (ax2 - ax1) * (ay2 - ay1))
        area_b = max(1.0, (bx2 - bx1) * (by2 - by1))
        return inter_area / (area_a + area_b - inter_area)

    def _nms(self, detections: list[dict[str, Any]], iou_threshold: float) -> list[dict[str, Any]]:
        kept: list[dict[str, Any]] = []
        for item in sorted(detections, key=lambda detection: detection["conf"], reverse=True):
            if all(self._iou(item["bbox"], other["bbox"]) <= iou_threshold for other in kept):
                kept.append(item)
        return kept

    @staticmethod
    def _draw_box(image: np.ndarray, label: str, score: float, bbox: list[float], color: tuple[int, int, int]) -> None:
        x1, y1, x2, y2 = [int(v) for v in bbox]
        cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)
        text = f"{label} {score:.2f}"
        text_bbox = LABEL_FONT.getbbox(text)
        text_w = text_bbox[2] - text_bbox[0]
        text_h = text_bbox[3] - text_bbox[1]
        label_height = text_h + 10
        label_top = y1 - label_height if y1 >= label_height else y1
        label_bottom = min(image.shape[0], label_top + label_height)
        label_right = min(image.shape[1], x1 + text_w + 10)
        cv2.rectangle(image, (x1, label_top), (label_right, label_bottom), color, -1)

        region = image[label_top:label_bottom, x1:label_right]
        if region.size:
            pil_region = Image.fromarray(cv2.cvtColor(region, cv2.COLOR_BGR2RGB))
            ImageDraw.Draw(pil_region).text((5, 3 - text_bbox[1]), text, font=LABEL_FONT, fill=(255, 255, 255))
            region[:] = cv2.cvtColor(np.asarray(pil_region), cv2.COLOR_RGB2BGR)


wall_detector = WallDetector()
