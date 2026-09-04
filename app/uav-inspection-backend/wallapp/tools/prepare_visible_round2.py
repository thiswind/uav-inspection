from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
from pathlib import Path

import cv2
import numpy as np


DEFAULT_SOURCE = Path(r"C:\Users\DL-X17R2\Desktop\无人机数据\外墙\data")
DEFAULT_WORKSPACE = Path(r"C:\Users\DL-X17R2\Desktop\无人机数据\外墙\annotation_workspace")
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare a dense visible-light facade annotation batch.")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    parser.add_argument("--long-step-sec", type=float, default=1.0)
    parser.add_argument("--short-step-sec", type=float, default=0.5)
    parser.add_argument("--short-video-sec", type=float, default=60.0)
    parser.add_argument("--max-edge", type=int, default=1920)
    parser.add_argument("--jpeg-quality", type=int, default=92)
    parser.add_argument("--similarity-distance", type=int, default=2)
    parser.add_argument("--clean", action="store_true", help="Clear round-two images before preparing.")
    return parser.parse_args()


def safe_name(value: str) -> str:
    normalized = re.sub(r"[^0-9A-Za-z_-]+", "_", value).strip("_")
    return normalized or "facade"


def is_infrared_video(path: Path) -> bool:
    return bool(re.search(r"(?:^|_)T$", path.stem, flags=re.IGNORECASE))


def file_signature(path: Path) -> str:
    digest = hashlib.sha1()
    digest.update(str(path.stat().st_size).encode())
    with path.open("rb") as stream:
        digest.update(stream.read(4 * 1024 * 1024))
    return digest.hexdigest()


def read_image(path: Path) -> np.ndarray | None:
    return cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)


def resize_image(image: np.ndarray, max_edge: int) -> np.ndarray:
    height, width = image.shape[:2]
    edge = max(height, width)
    if max_edge <= 0 or edge <= max_edge:
        return image
    scale = max_edge / edge
    return cv2.resize(image, (round(width * scale), round(height * scale)), interpolation=cv2.INTER_AREA)


def difference_hash(image: np.ndarray) -> int:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    sample = cv2.resize(gray, (9, 8), interpolation=cv2.INTER_AREA)
    bits = sample[:, 1:] > sample[:, :-1]
    value = 0
    for bit in bits.flatten():
        value = (value << 1) | int(bit)
    return value


def hamming_distance(first: int, second: int) -> int:
    return (first ^ second).bit_count()


def is_useful_frame(image: np.ndarray) -> tuple[bool, str]:
    gray = cv2.cvtColor(cv2.resize(image, (160, 90), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY)
    dark_ratio = float((gray < 18).mean())
    bright_ratio = float((gray > 245).mean())
    if float(gray.std()) < 10:
        return False, "low_texture"
    if dark_ratio > 0.72:
        return False, "mostly_dark"
    if bright_ratio > 0.78:
        return False, "mostly_bright"
    return True, ""


def write_jpeg(path: Path, image: np.ndarray, quality: int) -> None:
    ok, encoded = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise RuntimeError(f"Failed to encode image: {path}")
    encoded.tofile(path)


def existing_labeled_hashes(workspace: Path) -> list[int]:
    image_dir = workspace / "images" / "to_label"
    label_dir = workspace / "labels" / "to_label"
    image_by_stem = {path.stem.lower(): path for path in image_dir.glob("*.jpg")}
    hashes: list[int] = []
    for label in label_dir.glob("*.txt"):
        image_path = image_by_stem.get(label.stem.lower())
        if image_path is None:
            continue
        image = read_image(image_path)
        if image is not None:
            hashes.append(difference_hash(image))
    return hashes


def main() -> None:
    args = parse_args()
    source = args.source.resolve()
    workspace = args.workspace.resolve()
    output_dir = workspace / "images" / "round2_visible"
    label_dir = workspace / "labels" / "round2_visible"
    report_dir = workspace / "reports"
    manifest_path = report_dir / "round2_visible_manifest.csv"
    audit_path = report_dir / "round2_visible_audit.json"

    if not source.exists():
        raise FileNotFoundError(f"Source directory not found: {source}")
    if args.clean:
        shutil.rmtree(output_dir, ignore_errors=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    label_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)

    labeled_hashes = existing_labeled_hashes(workspace)
    accepted_hashes: list[int] = []
    rows: list[dict[str, object]] = []
    audit: dict[str, object] = {
        "source": str(source),
        "infrared_videos_excluded": [],
        "duplicate_videos_excluded": [],
        "visible_videos": [],
        "skip_counts": {},
    }
    skip_counts: dict[str, int] = {}

    def skip(reason: str) -> None:
        skip_counts[reason] = skip_counts.get(reason, 0) + 1

    def accept_image(image: np.ndarray) -> tuple[bool, int, str]:
        useful, reason = is_useful_frame(image)
        if not useful:
            return False, 0, reason
        image_hash = difference_hash(image)
        if any(hamming_distance(image_hash, known_hash) <= args.similarity_distance for known_hash in labeled_hashes):
            return False, image_hash, "already_labeled_or_near_duplicate"
        if any(hamming_distance(image_hash, known_hash) <= args.similarity_distance for known_hash in accepted_hashes):
            return False, image_hash, "round2_near_duplicate"
        return True, image_hash, ""

    media_files = sorted(path for path in source.rglob("*") if path.is_file())
    for path in media_files:
        suffix = path.suffix.lower()
        if suffix not in IMAGE_EXTENSIONS:
            continue
        image = read_image(path)
        if image is None:
            skip("unreadable_image")
            continue
        accepted, image_hash, reason = accept_image(image)
        if not accepted:
            skip(reason)
            continue
        image = resize_image(image, args.max_edge)
        name = f"r2_photo_{safe_name(str(path.relative_to(source).with_suffix('')))}.jpg"
        write_jpeg(output_dir / name, image, args.jpeg_quality)
        accepted_hashes.append(image_hash)
        rows.append({"image": name, "kind": "image", "source": str(path), "time_sec": "", "frame": ""})

    seen_video_signatures: dict[str, Path] = {}
    for path in media_files:
        if path.suffix.lower() not in VIDEO_EXTENSIONS:
            continue
        if is_infrared_video(path):
            audit["infrared_videos_excluded"].append(str(path))
            continue
        signature = file_signature(path)
        if signature in seen_video_signatures:
            audit["duplicate_videos_excluded"].append({
                "path": str(path),
                "duplicate_of": str(seen_video_signatures[signature]),
            })
            continue
        seen_video_signatures[signature] = path

        capture = cv2.VideoCapture(str(path))
        if not capture.isOpened():
            skip("unreadable_video")
            continue
        fps = float(capture.get(cv2.CAP_PROP_FPS) or 0)
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        duration = frame_count / fps if fps > 0 else 0
        if width <= height or width / max(1, height) < 1.45:
            audit["infrared_videos_excluded"].append(str(path))
            capture.release()
            continue
        step_sec = args.short_step_sec if duration <= args.short_video_sec else args.long_step_sec
        audit["visible_videos"].append({
            "path": str(path),
            "duration_sec": round(duration, 3),
            "fps": round(fps, 3),
            "size": [width, height],
            "step_sec": step_sec,
        })

        sample_index = 0
        while sample_index * step_sec < duration:
            time_sec = sample_index * step_sec
            capture.set(cv2.CAP_PROP_POS_MSEC, time_sec * 1000)
            ok, frame = capture.read()
            sample_index += 1
            if not ok or frame is None:
                skip("unreadable_frame")
                continue
            accepted, image_hash, reason = accept_image(frame)
            if not accepted:
                skip(reason)
                continue
            frame_number = int(round(time_sec * fps))
            frame = resize_image(frame, args.max_edge)
            name = f"r2_video_{safe_name(str(path.relative_to(source).with_suffix('')))}_{frame_number:07d}.jpg"
            write_jpeg(output_dir / name, frame, args.jpeg_quality)
            accepted_hashes.append(image_hash)
            rows.append({
                "image": name,
                "kind": "video",
                "source": str(path),
                "time_sec": f"{time_sec:.3f}",
                "frame": frame_number,
            })
        capture.release()

    with manifest_path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=["image", "kind", "source", "time_sec", "frame"])
        writer.writeheader()
        writer.writerows(rows)

    audit["skip_counts"] = skip_counts
    audit["prepared_images"] = len(rows)
    audit["prepared_photos"] = sum(row["kind"] == "image" for row in rows)
    audit["prepared_video_frames"] = sum(row["kind"] == "video" for row in rows)
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"prepared={len(rows)}")
    print(f"photos={audit['prepared_photos']}")
    print(f"video_frames={audit['prepared_video_frames']}")
    print(f"images={output_dir}")
    print(f"labels={label_dir}")
    print(f"manifest={manifest_path}")
    print(f"audit={audit_path}")


if __name__ == "__main__":
    main()
