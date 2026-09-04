import base64
import os
import threading
import time
from typing import Generator, Iterable, List, Optional

from pestapp.services.pest_service import PestService
from pestapp.services.pest_store import pest_store

FALLBACK_JPEG_BASE64 = (
    "/9j/4AAQSkZJRgABAQAAAQABAAD/2wCEAAkGBxAQEBUQEBAVFRUWFRUVFRUVFRUVFRUWFxUV\n"
    "FRUYHSggGBolHRUVITEhJSkrLi4uFx8zODMtNygtLisBCgoKDg0OGxAQGyslICUtLS0t\n"
    "LS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLf/AABEIAKgBLAMBIgACEQED\n"
    "EQH/xAAbAAACAwEBAQAAAAAAAAAAAAADBAACBQYBB//EADsQAAIBAgMFBgQEBgIDAAAAAAECAAMR\n"
    "BBIhMQVBUQYiYXGBEzKRobHB0fAjQlJy4fEWJDRDU4KS/8QAGQEBAAMBAQAAAAAAAAAAAAAAAAID\n"
    "BAEF/8QAJREAAgICAQQCAwAAAAAAAAAAAAECEQMhBBIxQVEiMmFx/9oADAMBAAIRAxEAPwD6sA=="
)


class FrameBuffer:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._frame: Optional[bytes] = None

    def update(self, frame_bytes: bytes) -> None:
        with self._lock:
            self._frame = frame_bytes

    def get(self) -> Optional[bytes]:
        with self._lock:
            return self._frame


frame_buffer = FrameBuffer()


class FrameProvider:
    def iter_frames(self) -> Iterable[bytes]:
        raise NotImplementedError


class DirectoryFrameProvider(FrameProvider):
    def __init__(self, frames_dir: str) -> None:
        self.frames_dir = frames_dir
        self.frame_files = self._list_frame_files()

    def _list_frame_files(self) -> List[str]:
        if not os.path.isdir(self.frames_dir):
            return []

        candidates = []
        for name in os.listdir(self.frames_dir):
            lower = name.lower()
            if lower.endswith(".jpg") or lower.endswith(".jpeg"):
                candidates.append(os.path.join(self.frames_dir, name))

        return sorted(candidates)

    def iter_frames(self) -> Iterable[bytes]:
        index = 0
        while True:
            frame_path = self.frame_files[index]
            with open(frame_path, "rb") as file:
                frame = file.read()
            yield frame
            index = (index + 1) % len(self.frame_files)


class Mp4FrameProvider(FrameProvider):
    def __init__(self, file_path: str) -> None:
        self.file_path = file_path
        self.cv2 = self._try_import_cv2()

    def _try_import_cv2(self):
        try:
            import cv2  # type: ignore
            return cv2
        except Exception:
            return None

    def iter_frames(self) -> Iterable[bytes]:
        if not self.cv2:
            raise RuntimeError("opencv-python not installed")

        capture = self.cv2.VideoCapture(self.file_path)
        if not capture.isOpened():
            capture.release()
            raise RuntimeError("Unable to open video file")
        fail_count = 0
        try:
            while True:
                success, frame = capture.read()
                if not success:
                    fail_count += 1
                    if fail_count >= 10:
                        raise RuntimeError("Unable to read frames from video")
                    capture.set(self.cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                fail_count = 0
                success, encoded = self.cv2.imencode(".jpg", frame)
                if not success:
                    continue
                yield encoded.tobytes()
        finally:
            capture.release()


class MockFrameProvider(FrameProvider):
    def __init__(self) -> None:
        self._frame = base64.b64decode(FALLBACK_JPEG_BASE64)

    def iter_frames(self) -> Iterable[bytes]:
        while True:
            yield self._frame


def _get_frames_dir(route_id: Optional[str] = None) -> str:
    base_dir = PestService._get_base_data_dir()
    if route_id:
        route_dir = os.path.join(base_dir, "media", "frames", route_id)
        if os.path.isdir(route_dir):
            return route_dir
    return os.path.join(base_dir, "media", "frames")


def _get_video_path(route_id: Optional[str] = None) -> str:
    base_dir = PestService._get_base_data_dir()
    video_file = None
    if route_id:
        route = pest_store.get_route(route_id)
        if route:
            video_file = route.get("video_file")
    if not video_file:
        return os.path.join(base_dir, "media")
    return os.path.join(base_dir, "media", video_file)


def _find_first_video_file() -> Optional[str]:
    base_dir = PestService._get_base_data_dir()
    media_dir = os.path.join(base_dir, "media")
    if not os.path.isdir(media_dir):
        return None

    for name in sorted(os.listdir(media_dir)):
        lower = name.lower()
        if lower.endswith(".mp4") or lower.endswith(".mov"):
            return os.path.join(media_dir, name)
    return None


def resolve_video_path(route_id: Optional[str] = None) -> str:
    video_path = _get_video_path(route_id)
    if os.path.isfile(video_path):
        return video_path

    if route_id:
        default_path = _get_video_path(None)
        if os.path.isfile(default_path):
            return default_path

    fallback = _find_first_video_file()
    if fallback:
        return fallback
    return video_path


def _select_frame_provider(route_id: Optional[str] = None) -> FrameProvider:
    frames_dir = _get_frames_dir(route_id)
    directory_provider = DirectoryFrameProvider(frames_dir)
    if directory_provider.frame_files:
        return directory_provider

    video_path = resolve_video_path(route_id)
    if os.path.exists(video_path):
        provider = Mp4FrameProvider(video_path)
        if provider.cv2:
            return provider

    return MockFrameProvider()


def push_frame(frame_bytes: bytes) -> None:
    frame_buffer.update(frame_bytes)


def iter_mjpeg_frames(route_id: Optional[str] = None, delay_sec: float = 0.12) -> Generator[bytes, None, None]:
    provider = _select_frame_provider(route_id)
    provider_iter = provider.iter_frames()

    while True:
        frame = frame_buffer.get()
        if frame is None:
            try:
                frame = next(provider_iter)
            except StopIteration:
                provider_iter = provider.iter_frames()
                continue
            except Exception:
                provider_iter = MockFrameProvider().iter_frames()
                frame = next(provider_iter)

        yield _format_mjpeg_chunk(frame)
        time.sleep(delay_sec)


def _format_mjpeg_chunk(frame_bytes: bytes) -> bytes:
    return (
        b"--frame\r\n"
        b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
    )
