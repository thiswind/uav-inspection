from __future__ import annotations

import base64
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from deployment_paths import backend_path
from optional_inference import inference_device, load_yolo_model

MODEL_PATH = backend_path('treeapp', 'tree-pruning-best.pt')

CLASS_NAMES = {
    0: 'Pruned',
    1: 'PrunedTree',
    2: 'Unpruned',
}

CLASS_CN = {
    0: '已修剪',
    1: '已修剪(树)',
    2: '未修剪',
}

CLASS_COLORS = {
    'Pruned': (34, 197, 94),
    'PrunedTree': (16, 185, 129),
    'Unpruned': (239, 68, 68),
}


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _feature_score(value: float, low: float, high: float) -> float:
    if high <= low:
        return 0.0
    return _clamp01((value - low) / (high - low))


class TreePruningDetector:
    _instance: 'TreePruningDetector | None' = None

    def __new__(cls) -> 'TreePruningDetector':
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

        results = self.model(image_bgr, conf=conf, iou=iou, verbose=False, device=self.device)
        detections: list[dict[str, Any]] = []
        stats = {'Pruned': 0, 'Unpruned': 0}
        annotated = image_bgr.copy()

        for result in results:
            boxes = result.boxes
            if boxes is None:
                continue

            mask_points = []
            if result.masks is not None:
                try:
                    mask_points = list(result.masks.xy)
                except Exception:
                    mask_points = []

            for index in range(len(boxes)):
                cls_id = int(boxes.cls[index].item())
                if cls_id not in CLASS_NAMES:
                    continue

                score = float(boxes.conf[index].item())
                x1, y1, x2, y2 = [float(v) for v in boxes.xyxy[index].tolist()]
                label = CLASS_NAMES[cls_id]
                color = CLASS_COLORS[label]
                summary_label = 'Unpruned' if label == 'Unpruned' else 'Pruned'
                stats[summary_label] += 1

                detections.append({
                    'class': cls_id,
                    'name': label,
                    'summary_name': summary_label,
                    'cn': CLASS_CN[cls_id],
                    'bbox': [round(x1, 1), round(y1, 1), round(x2, 1), round(y2, 1)],
                    'conf': round(score, 3),
                })

                contour = mask_points[index] if index < len(mask_points) else None
                self._draw_detection(annotated, CLASS_CN[cls_id], score, (x1, y1, x2, y2), color, contour)

        assessment = self._assess_pruning_need(image_bgr, detections)
        self._draw_assessment(annotated, assessment)

        _, buffer = cv2.imencode('.jpg', annotated)
        annotated_base64 = base64.b64encode(buffer).decode('utf-8')
        inference_ms = round((time.perf_counter() - started_at) * 1000, 2)

        return {
            'detections': detections,
            'count': len(detections),
            'stats': stats,
            'pruning_assessment': assessment,
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

    def is_model_available(self) -> bool:
        return MODEL_PATH.exists()

    def get_info(self) -> dict[str, Any]:
        return {
            'system': {
                'cuda_available': self.device.startswith('cuda'),
                'device': self.device,
            },
            'model': {
                'name': MODEL_PATH.name,
                'available': self.is_model_available(),
                'loaded': self.model is not None,
                'classes': list(CLASS_CN.values()),
            },
            'config': {
                'confidence': self.conf_threshold,
                'iou': self.iou_threshold,
            },
            'capabilities': {
                'video_file': True,
                'single_frame_detection': True,
                'segmentation_overlay': True,
                'feature_fusion': True,
            },
        }

    def _assess_pruning_need(self, image_bgr: np.ndarray, detections: list[dict[str, Any]]) -> dict[str, Any]:
        features = self._analyze_pruning_features(image_bgr)

        pruned_conf = 0.0
        unpruned_conf = 0.0
        for item in detections:
            conf = float(item.get('conf', 0.0))
            if item.get('summary_name') == 'Unpruned':
                unpruned_conf = max(unpruned_conf, conf)
            else:
                pruned_conf = max(pruned_conf, conf)

        if pruned_conf > 0 or unpruned_conf > 0:
            model_score = _clamp01(0.5 + 0.52 * unpruned_conf - 0.42 * pruned_conf)
        else:
            model_score = 0.32

        feature_score = _clamp01(
            0.42 * features['branch_score']
            + 0.34 * features['leaf_score']
            + 0.24 * features['yellow_leaf_score']
        )
        score = _clamp01(0.56 * model_score + 0.44 * feature_score)
        needs_pruning = score >= 0.55

        if score >= 0.74:
            level = 'high'
        elif score >= 0.55:
            level = 'medium'
        else:
            level = 'low'

        reasons = self._build_assessment_reasons(
            needs_pruning=needs_pruning,
            pruned_conf=pruned_conf,
            unpruned_conf=unpruned_conf,
            features=features,
        )

        return {
            'needs_pruning': needs_pruning,
            'decision': '建议修剪' if needs_pruning else '暂不建议修剪',
            'level': level,
            'score': round(score, 3),
            'feature_score': round(feature_score, 3),
            'model_vote': {
                'score': round(model_score, 3),
                'pruned_conf': round(pruned_conf, 3),
                'unpruned_conf': round(unpruned_conf, 3),
            },
            'features': {
                'branch_density': round(features['branch_density'], 4),
                'leaf_coverage': round(features['leaf_coverage'], 4),
                'yellow_leaf_ratio': round(features['yellow_leaf_ratio'], 4),
                'branch_score': round(features['branch_score'], 3),
                'leaf_score': round(features['leaf_score'], 3),
                'yellow_leaf_score': round(features['yellow_leaf_score'], 3),
            },
            'reasons': reasons,
        }

    @staticmethod
    def _analyze_pruning_features(image_bgr: np.ndarray) -> dict[str, float]:
        max_side = 640
        height, width = image_bgr.shape[:2]
        longest = max(width, height)
        if longest > max_side:
            scale = max_side / longest
            image_bgr = cv2.resize(image_bgr, (round(width * scale), round(height * scale)), interpolation=cv2.INTER_AREA)

        hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)
        green_leaf = cv2.inRange(hsv, np.array([35, 35, 35]), np.array([95, 255, 255]))
        yellow_leaf = cv2.inRange(hsv, np.array([18, 45, 70]), np.array([38, 255, 255]))
        bark = cv2.inRange(hsv, np.array([4, 28, 30]), np.array([28, 180, 190]))

        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        leaf_mask = cv2.bitwise_or(green_leaf, yellow_leaf)
        leaf_mask = cv2.morphologyEx(leaf_mask, cv2.MORPH_OPEN, kernel, iterations=1)
        leaf_mask = cv2.morphologyEx(leaf_mask, cv2.MORPH_CLOSE, kernel, iterations=1)

        vegetation_or_branch = cv2.bitwise_or(leaf_mask, bark)
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (3, 3), 0)
        edges = cv2.Canny(gray, 55, 145)
        branch_edges = cv2.bitwise_and(edges, vegetation_or_branch)

        frame_area = max(1, image_bgr.shape[0] * image_bgr.shape[1])
        leaf_pixels = cv2.countNonZero(leaf_mask)
        yellow_pixels = cv2.countNonZero(cv2.bitwise_and(yellow_leaf, leaf_mask))
        support_pixels = max(cv2.countNonZero(vegetation_or_branch), 1)

        leaf_coverage = leaf_pixels / frame_area
        yellow_leaf_ratio = yellow_pixels / max(leaf_pixels, 1)
        branch_density = cv2.countNonZero(branch_edges) / support_pixels

        return {
            'branch_density': branch_density,
            'leaf_coverage': leaf_coverage,
            'yellow_leaf_ratio': yellow_leaf_ratio,
            'branch_score': _feature_score(branch_density, 0.045, 0.16),
            'leaf_score': _feature_score(leaf_coverage, 0.24, 0.58),
            'yellow_leaf_score': _feature_score(yellow_leaf_ratio, 0.08, 0.32),
        }

    @staticmethod
    def _build_assessment_reasons(
        *,
        needs_pruning: bool,
        pruned_conf: float,
        unpruned_conf: float,
        features: dict[str, float],
    ) -> list[str]:
        reasons: list[str] = []

        if unpruned_conf >= 0.35 and unpruned_conf >= pruned_conf:
            reasons.append(f'现有模型倾向未修剪，最高置信度 {unpruned_conf:.2f}')
        elif pruned_conf >= 0.35:
            reasons.append(f'现有模型倾向已修剪，最高置信度 {pruned_conf:.2f}')
        else:
            reasons.append('现有模型目标置信度偏低，启用视觉特征补充判定')

        if features['branch_score'] >= 0.55:
            reasons.append('分支纹理较密，疑似分支过多')
        if features['leaf_score'] >= 0.55:
            reasons.append('叶面覆盖量较大，疑似枝叶过密')
        if features['yellow_leaf_score'] >= 0.45:
            reasons.append('叶片偏黄比例升高，需要结合养护状态复核')

        if not needs_pruning and len(reasons) == 1:
            reasons.append('分支、叶量与黄叶特征未达到修剪阈值')

        return reasons[:4]

    @staticmethod
    def _draw_assessment(image: np.ndarray, assessment: dict[str, Any]) -> None:
        decision = 'PRUNE' if assessment['needs_pruning'] else 'OK'
        score = assessment['score']
        features = assessment['features']
        lines = [
            f'{decision}  score {score:.2f}',
            f"branch {features['branch_score']:.2f} leaf {features['leaf_score']:.2f}",
            f"yellow {features['yellow_leaf_score']:.2f}",
        ]
        color = (239, 68, 68) if assessment['needs_pruning'] else (34, 197, 94)
        font = cv2.FONT_HERSHEY_SIMPLEX
        width = 250
        height = 24 + len(lines) * 24
        overlay = image.copy()
        cv2.rectangle(overlay, (12, 12), (12 + width, 12 + height), (15, 23, 42), -1)
        cv2.addWeighted(overlay, 0.72, image, 0.28, 0, image)
        cv2.rectangle(image, (12, 12), (12 + width, 12 + height), color, 2)
        for index, line in enumerate(lines):
            cv2.putText(image, line, (24, 42 + index * 24), font, 0.58, (255, 255, 255), 2, cv2.LINE_AA)

    @staticmethod
    def _draw_detection(
        image: np.ndarray,
        label: str,
        score: float,
        bbox: tuple[float, float, float, float],
        color: tuple[int, int, int],
        contour: Any | None,
    ) -> None:
        x1, y1, x2, y2 = [int(v) for v in bbox]
        if contour is not None:
            contour_np = np.array(contour, dtype=np.int32)
            if contour_np.ndim == 2 and len(contour_np) >= 3:
                cv2.drawContours(image, [contour_np], -1, color, 2)
        cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)
        text = f'{label} {score:.2f}'
        font = cv2.FONT_HERSHEY_SIMPLEX
        text_size, _ = cv2.getTextSize(text, font, 0.6, 2)
        text_w, text_h = text_size
        cv2.rectangle(image, (x1, max(0, y1 - text_h - 10)), (x1 + text_w + 8, y1), color, -1)
        cv2.putText(image, text, (x1 + 4, y1 - 6), font, 0.6, (255, 255, 255), 2, cv2.LINE_AA)


tree_pruning_detector = TreePruningDetector()
