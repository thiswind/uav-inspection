import cv2
import os
import asyncio
import numpy as np
import math
import logging
import concurrent.futures
from typing import Dict, Any, Optional
from datetime import datetime
from deployment_paths import BACKEND_DATA_ROOT, backend_path
from optional_inference import InferenceUnavailableError, load_yolo_model
from heatmapapp.utils.srt_parser import parse_dji_srt_file
from heatmapapp.services.gis_solver import pixel_to_wgs84
from heatmapapp.services.task_manager import task_manager, TaskStatus

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AI-Inference")

PERSON_CONFIDENCE = 0.08
PERSON_MIN_LABEL_CONFIDENCE = 0.12
PERSON_INFERENCE_SIZE = 1536


def _is_valid_aerial_person_box(box, confidence: float, img_width: int, img_height: int) -> bool:
    x1, y1, x2, y2 = [float(v) for v in box]
    width = max(0.0, x2 - x1)
    height = max(0.0, y2 - y1)
    if confidence < PERSON_MIN_LABEL_CONFIDENCE or width <= 0 or height <= 0:
        return False

    scale_x = img_width / 3840.0
    scale_y = img_height / 2160.0
    min_w = max(10.0, 14.0 * scale_x)
    min_h = max(10.0, 14.0 * scale_y)
    max_w = max(72.0, 130.0 * scale_x)
    max_h = max(72.0, 130.0 * scale_y)
    min_area = max(80.0, 180.0 * scale_x * scale_y)
    max_area = max(2500.0, 11000.0 * scale_x * scale_y)
    aspect = width / max(height, 1.0)

    return (
        min_w <= width <= max_w
        and min_h <= height <= max_h
        and min_area <= width * height <= max_area
        and 0.35 <= aspect <= 2.0
    )

class InferenceEngine:
    def __init__(self):
        self.hfov_deg = 80.0
        self.base_dir = str(BACKEND_DATA_ROOT)
        self.model_path = backend_path("heatmapweight", "renliu.pt")
        self.model = None
        self.model_error = None
        # snapshots 已关闭，告警不再生成截图

        # task_id -> state
        self.task_states: Dict[str, Dict[str, Any]] = {}
        self.processing_tasks: Dict[str, asyncio.Task] = {}

        self.alert_threshold = 10
        self.alert_cooldown_sec = 5

        self.tracker_config = "bytetrack.yaml"
        self.active_track_task_id = None

        # 单线程后台线程池，用于推理
        self.ai_executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)

    def ensure_model(self) -> None:
        """An absent optional model must not masquerade as zero detected people."""
        if self.model is not None:
            return
        try:
            self.model = load_yolo_model(self.model_path)
            self.model_error = None
            logger.info("模型加载成功: %s", self.model_path)
        except InferenceUnavailableError as exc:
            self.model_error = str(exc)
            raise

    def _reset_track_state(self):
        if not self.model:
            return
        if hasattr(self.model, "tracker"):
            self.model.tracker = None
        if hasattr(self.model, "predictor") and hasattr(self.model.predictor, "tracker"):
            self.model.predictor.tracker = None

    def _ensure_task_state(self, task_id: str) -> Dict[str, Any]:
        if task_id not in self.task_states:
            self.task_states[task_id] = {
                "taskId": task_id,
                "fps": 30.0,
                "totalFrames": 0,
                "latestStats": {
                    "frameId": 0,
                    "totalCount": 0,
                    "telemetry": {},
                    "targets": [],
                    "fps": 30.0,
                    "totalFrames": 0
                },
                "telemetryData": {},
                "trackingData": {},
                "frameCounts": {},
                "alerts": [],
                "isProcessing": False,
                "isCompleted": False,
                "lastAlertFrame": -999999,
                "progress": 0
            }
        return self.task_states[task_id]

    def _run_ai_task(self, frame, curr_tel, w, h):
        if not self.model:
            return []

        try:
            results = self.model.track(
                frame,
                verbose=False,
                persist=True,
                tracker=self.tracker_config,
                conf=0.15,      # 降低阈值以提高检测灵敏度
                iou=0.5,        # NMS IoU 阈值
            )
        except Exception as exc:
            logger.warning("Track failed, fallback to predict: %s", exc)
            results = self.model.predict(frame, verbose=False, conf=0.15, iou=0.5)

        targets = []
        if not results or results[0].boxes is None:
            return targets

        boxes = results[0].boxes
        xyxy = boxes.xyxy.cpu().numpy() if hasattr(boxes.xyxy, "cpu") else np.array(boxes.xyxy)
        confs = boxes.conf.cpu().numpy() if getattr(boxes, "conf", None) is not None else None
        clss = boxes.cls.cpu().numpy() if getattr(boxes, "cls", None) is not None else None
        ids = boxes.id.cpu().numpy() if getattr(boxes, "id", None) is not None else None

        for idx, box in enumerate(xyxy):
            x1, y1, x2, y2 = box
            bbox = [float(x1), float(y1), float(x2), float(y2)]
            g_lat, g_lon = pixel_to_wgs84(bbox, curr_tel, img_width=w, img_height=h, hfov_deg=self.hfov_deg)
            track_id = int(ids[idx]) if ids is not None else int(idx)
            class_id = int(clss[idx]) if clss is not None else 0
            confidence = float(confs[idx]) if confs is not None else 0.0
            targets.append({
                "trackId": track_id,
                "classId": class_id,
                "confidence": confidence,
                "bbox": bbox,
                "geoLat": float(g_lat),
                "geoLon": float(g_lon)
            })
        return targets

    def _run_ai_task(self, frame, curr_tel, w, h):
        if not self.model:
            return []

        try:
            results = self.model.track(
                frame,
                verbose=False,
                persist=True,
                tracker=self.tracker_config,
                conf=PERSON_CONFIDENCE,
                iou=0.45,
                imgsz=PERSON_INFERENCE_SIZE,
                classes=[0],
                max_det=220,
            )
        except Exception as exc:
            logger.warning("Track failed, fallback to predict: %s", exc)
            results = self.model.predict(
                frame,
                verbose=False,
                conf=PERSON_CONFIDENCE,
                iou=0.45,
                imgsz=PERSON_INFERENCE_SIZE,
                classes=[0],
                max_det=220,
            )

        targets = []
        if not results or results[0].boxes is None:
            return targets

        boxes = results[0].boxes
        xyxy = boxes.xyxy.cpu().numpy() if hasattr(boxes.xyxy, "cpu") else np.array(boxes.xyxy)
        confs = boxes.conf.cpu().numpy() if getattr(boxes, "conf", None) is not None else None
        clss = boxes.cls.cpu().numpy() if getattr(boxes, "cls", None) is not None else None
        ids = boxes.id.cpu().numpy() if getattr(boxes, "id", None) is not None else None

        for idx, box in enumerate(xyxy):
            confidence = float(confs[idx]) if confs is not None else 0.0
            if not _is_valid_aerial_person_box(box, confidence, w, h):
                continue

            x1, y1, x2, y2 = box
            bbox = [float(x1), float(y1), float(x2), float(y2)]
            track_id = int(ids[idx]) if ids is not None else int(idx)
            class_id = int(clss[idx]) if clss is not None else 0
            target = {
                "trackId": track_id,
                "classId": class_id,
                "confidence": confidence,
                "bbox": bbox
            }
            if curr_tel:
                g_lat, g_lon = pixel_to_wgs84(bbox, curr_tel, img_width=w, img_height=h, hfov_deg=self.hfov_deg)
                target["geoLat"] = float(g_lat)
                target["geoLon"] = float(g_lon)
            targets.append(target)
        return targets

    def start_processing(self, task_id: str):
        existing = self.processing_tasks.get(task_id)
        if existing and not existing.done():
            return True
        if not task_manager.get_task(task_id):
            task_manager.create_task(task_id, f"巡检任务_{task_id}")
        try:
            self.ensure_model()
        except InferenceUnavailableError as exc:
            task_manager.update_status(task_id, TaskStatus.FAILED, error=str(exc))
            return False
        if self.active_track_task_id != task_id:
            self._reset_track_state()
            self.active_track_task_id = task_id
        if not task_manager.get_task(task_id):
            task_manager.create_task(task_id, f"巡检任务_{task_id}")
        task_manager.update_status(task_id, TaskStatus.PROCESSING, progress=0)
        loop = asyncio.get_running_loop()
        self.processing_tasks[task_id] = loop.create_task(self._process_video(task_id))
        return True

    def get_latest_stats(self, task_id: str) -> Dict[str, Any]:
        state = self._ensure_task_state(task_id)
        return state["latestStats"]

    def get_task_state(self, task_id: str) -> Dict[str, Any]:
        return self._ensure_task_state(task_id)

    def get_task_result(self, task_id: str) -> Optional[Dict[str, Any]]:
        if task_id not in self.task_states:
            return None
        state = self.task_states[task_id]
        return {
            "fps": state["fps"],
            "totalFrames": state["totalFrames"],
            "telemetryData": list(state["telemetryData"].values()),
            "trackingData": state["trackingData"],
            "alerts": state["alerts"],
            "frameCounts": state["frameCounts"],
            "isCompleted": state["isCompleted"]
        }

    async def discard_task(self, task_id: str) -> None:
        processing_task = self.processing_tasks.pop(task_id, None)
        if processing_task and not processing_task.done():
            processing_task.cancel()
            try:
                await processing_task
            except asyncio.CancelledError:
                pass

        self.task_states.pop(task_id, None)
        if self.active_track_task_id == task_id:
            self.active_track_task_id = None
            self._reset_track_state()

    async def _process_video(self, task_id: str):
        state = self._ensure_task_state(task_id)
        state["isProcessing"] = True
        state["progress"] = 0

        video_path = os.path.join(self.base_dir, "heatmapdata", "videos", f"{task_id}.mp4")
        srt_path = os.path.join(self.base_dir, "heatmapdata", "videos", f"{task_id}.srt")
        if not os.path.exists(video_path):
            state["isProcessing"] = False
            task_manager.update_status(task_id, TaskStatus.FAILED, error="video missing")
            return

        telemetry_data = parse_dji_srt_file(srt_path) if os.path.exists(srt_path) else {}
        state["telemetryData"] = telemetry_data

        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 1920
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 1080

        state["fps"] = float(fps)
        state["totalFrames"] = total_frames
        state["latestStats"]["fps"] = float(fps)
        state["latestStats"]["totalFrames"] = total_frames

        frame_idx = 0
        last_tel = None
        last_tel_frame = None
        max_stale_telemetry_frames = max(1, int(fps * 2))
        loop = asyncio.get_running_loop()

        try:
            while cap.isOpened():
                success, frame = cap.read()
                if not success:
                    break
                frame_idx += 1

                exact_tel = telemetry_data.get(frame_idx)
                if exact_tel:
                    last_tel = exact_tel
                    last_tel_frame = frame_idx

                curr_tel = exact_tel or last_tel or {}
                geo_tel = exact_tel
                if (
                    geo_tel is None
                    and last_tel
                    and last_tel_frame is not None
                    and frame_idx - last_tel_frame <= max_stale_telemetry_frames
                ):
                    geo_tel = last_tel

                targets = await loop.run_in_executor(
                    self.ai_executor, self._run_ai_task, frame.copy(), geo_tel, w, h
                )

                state["trackingData"][frame_idx] = targets
                state["frameCounts"][frame_idx] = len(targets)

                # 每 30 帧输出一次检测统计
                if frame_idx % 30 == 0:
                    logger.info("[%s] 已处理 %d/%d 帧, 当前帧检测到 %d 个目标",
                                task_id[:10], frame_idx, total_frames, len(targets))

                state["latestStats"] = {
                    "frameId": frame_idx,
                    "totalCount": len(targets),
                    "telemetry": curr_tel,
                    "targets": targets,
                    "fps": float(fps),
                    "totalFrames": total_frames
                }

                if total_frames > 0:
                    progress = int((frame_idx / total_frames) * 100)
                    if progress != state.get("progress"):
                        state["progress"] = progress
                        task_manager.update_status(task_id, TaskStatus.PROCESSING, progress=progress)

                alert = self._maybe_create_alert(task_id, frame_idx, curr_tel, len(targets), frame, fps)
                if alert:
                    state["latestStats"]["alert"] = alert

            state["isProcessing"] = False
            state["isCompleted"] = True
            total_detections = sum(state["frameCounts"].values())
            logger.info("[%s] ✅ 推理完成: %d 帧, 共检测到 %d 个目标实例",
                        task_id[:10], frame_idx, total_detections)
        except Exception as exc:
            logger.exception("Processing failed for %s", task_id)
            state["isProcessing"] = False
            state["isCompleted"] = False
            task_manager.update_status(task_id, TaskStatus.FAILED, error=str(exc))
        finally:
            cap.release()

        if state["isCompleted"]:
            task_manager.update_status(task_id, TaskStatus.COMPLETED, progress=100)

    def _maybe_create_alert(self, task_id: str, frame_id: int, telemetry: Dict[str, Any], count: int, frame, fps: float):
        state = self._ensure_task_state(task_id)
        min_gap_frames = int(self.alert_cooldown_sec * fps)
        if count < self.alert_threshold:
            return None
        if frame_id - state["lastAlertFrame"] < min_gap_frames:
            return None

        state["lastAlertFrame"] = frame_id
        alert_id = f"alert_{task_id}_{frame_id}"
        timestamp = telemetry.get("timestamp") or datetime.now().strftime("%H:%M:%S")

        alert = {
            "id": alert_id,
            "timestamp": timestamp,
            "frameId": frame_id,
            "type": "CROWD_DENSITY",
            "count": count,
            "threshold": self.alert_threshold,
            "centerLat": telemetry.get("latitude", 0),
            "centerLon": telemetry.get("longitude", 0),
            "snapshotUrl": None,
            "isRead": False
        }
        state["alerts"].insert(0, alert)
        return alert

    async def run_stream(self, task_id: str):
        # 兼容老 MJPEG 接口，仍然会驱动同一套处理逻辑
        self.ensure_model()
        video_path = os.path.join(self.base_dir, "heatmapdata", "videos", f"{task_id}.mp4")
        srt_path = os.path.join(self.base_dir, "heatmapdata", "videos", f"{task_id}.srt")
        if not os.path.exists(video_path):
            return

        if self.active_track_task_id != task_id:
            self._reset_track_state()
            self.active_track_task_id = task_id

        state = self._ensure_task_state(task_id)
        telemetry_data = parse_dji_srt_file(srt_path) if os.path.exists(srt_path) else {}
        state["telemetryData"] = telemetry_data

        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 1920
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 1080

        state["fps"] = float(fps)
        state["totalFrames"] = total_frames
        state["latestStats"]["fps"] = float(fps)
        state["latestStats"]["totalFrames"] = total_frames

        frame_idx = 0
        last_tel = None
        last_tel_frame = None
        max_stale_telemetry_frames = max(1, int(fps * 2))
        loop = asyncio.get_running_loop()

        while cap.isOpened():
            success, frame = cap.read()
            if not success:
                break
            frame_idx += 1

            exact_tel = telemetry_data.get(frame_idx)
            if exact_tel:
                last_tel = exact_tel
                last_tel_frame = frame_idx

            curr_tel = exact_tel or last_tel or {}
            geo_tel = exact_tel
            if (
                geo_tel is None
                and last_tel
                and last_tel_frame is not None
                and frame_idx - last_tel_frame <= max_stale_telemetry_frames
            ):
                geo_tel = last_tel

            targets = await loop.run_in_executor(
                self.ai_executor, self._run_ai_task, frame.copy(), geo_tel, w, h
            )
            state["trackingData"][frame_idx] = targets
            state["frameCounts"][frame_idx] = len(targets)

            state["latestStats"] = {
                "frameId": frame_idx,
                "totalCount": len(targets),
                "telemetry": curr_tel,
                "targets": targets,
                "fps": float(fps),
                "totalFrames": total_frames
            }

            alert = self._maybe_create_alert(task_id, frame_idx, curr_tel, len(targets), frame, fps)
            if alert:
                state["latestStats"]["alert"] = alert

            for t in targets:
                x1, y1, x2, y2 = t["bbox"]
                pt1, pt2 = (int(x1), int(y1)), (int(x2), int(y2))
                cv2.rectangle(frame, pt1, pt2, (212, 182, 6), 2)

            ret, buffer = cv2.imencode('.jpg', frame)
            if ret:
                frame_bytes = buffer.tobytes()
                yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

            await asyncio.sleep(0.005)

        cap.release()

engine = InferenceEngine()
