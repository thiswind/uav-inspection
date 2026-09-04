from __future__ import annotations

import argparse
import json
import random
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import cv2
import numpy as np


BACKEND_DIR = Path(__file__).resolve().parents[2]
WALL_APP_DIR = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = Path.home() / "Desktop" / "\u65e0\u4eba\u673a\u6570\u636e" / "\u5916\u5899" / "data"
DEFAULT_OUTPUT = WALL_APP_DIR / "wall_damage_dataset"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp"}
VIDEO_SUFFIXES = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
CLASS_NAME = "TileSpalling"


@dataclass(frozen=True)
class Sample:
    image_path: Path
    label_path: Path
    boxes: list[tuple[int, int, int, int]]
    source: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare a YOLO dataset for facade damage detection.")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--image-size", type=int, default=1280, help="Longest side used when saving training frames.")
    parser.add_argument("--video-step-sec", type=float, default=2.0)
    parser.add_argument("--max-video-frames", type=int, default=90)
    parser.add_argument("--max-negative-video-frames", type=int, default=35)
    parser.add_argument("--val-ratio", type=float, default=0.22)
    parser.add_argument("--seed", type=int, default=20260709)
    parser.add_argument("--clean", action="store_true", help="Remove the output dataset before recreating it.")
    return parser.parse_args()


def imread_unicode(path: Path) -> np.ndarray | None:
    data = np.fromfile(str(path), dtype=np.uint8)
    if data.size == 0:
        return None
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def imwrite_unicode(path: Path, image: np.ndarray, quality: int = 92) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ext = ".jpg" if path.suffix.lower() in {"", ".jpg", ".jpeg"} else path.suffix
    ok, buffer = cv2.imencode(ext, image, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not ok:
        raise ValueError(f"Unable to encode image: {path}")
    buffer.tofile(str(path))


def resize_long_side(image: np.ndarray, max_side: int) -> np.ndarray:
    height, width = image.shape[:2]
    longest = max(height, width)
    if longest <= max_side:
        return image
    scale = max_side / longest
    return cv2.resize(image, (round(width * scale), round(height * scale)), interpolation=cv2.INTER_AREA)


def facade_damage_boxes(image_bgr: np.ndarray, analysis_side: int = 1280) -> list[tuple[int, int, int, int]]:
    original_height, original_width = image_bgr.shape[:2]
    scale = analysis_side / max(original_width, original_height) if max(original_width, original_height) > analysis_side else 1.0
    image = (
        cv2.resize(image_bgr, (round(original_width * scale), round(original_height * scale)), interpolation=cv2.INTER_AREA)
        if scale != 1.0
        else image_bgr.copy()
    )
    height, width = image.shape[:2]

    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    hue, saturation, value = cv2.split(hsv)
    _, channel_a, channel_b = cv2.split(lab)

    brick_mask = (
        (((hue <= 22) | (hue >= 172)) & (saturation >= 50) & (value >= 55) & (value <= 245))
        .astype(np.uint8)
        * 255
    )
    brick_mask = cv2.morphologyEx(
        brick_mask,
        cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5)),
        iterations=1,
    )
    brick_mask = cv2.morphologyEx(
        brick_mask,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_RECT, (21, 21)),
        iterations=2,
    )

    contours, _ = cv2.findContours(brick_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    region_mask = np.zeros((height, width), np.uint8)
    brick_regions: list[tuple[int, int, int, int, float]] = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if area > height * width * 0.018:
            x, y, box_w, box_h = cv2.boundingRect(contour)
            brick_regions.append((x, y, x + box_w, y + box_h, area))
            cv2.drawContours(region_mask, [contour], -1, 255, -1)

    if not brick_regions:
        return []

    support_mask = cv2.morphologyEx(
        region_mask,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_RECT, (61, 61)),
        iterations=2,
    )
    support_mask = cv2.dilate(
        support_mask,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (19, 19)),
        iterations=1,
    )

    chroma = np.sqrt((channel_a.astype(np.float32) - 128) ** 2 + (channel_b.astype(np.float32) - 128) ** 2)
    blue = (hue >= 78) & (hue <= 125) & (saturation > 45) & (value > 70)
    green = (hue >= 35) & (hue <= 90) & (saturation > 45) & (value > 60)
    sky_white = (saturation < 35) & (value > 220)

    non_brick_material = (
        (support_mask > 0)
        & (brick_mask == 0)
        & (value > 55)
        & (value < 235)
        & (saturation < 125)
        & ~blue
        & ~green
        & ~sky_white
    ).astype(np.uint8) * 255
    gray_material = (
        (support_mask > 0)
        & (saturation < 70)
        & (value > 75)
        & (value < 230)
        & (chroma < 30)
        & ~blue
        & ~green
    ).astype(np.uint8) * 255

    candidate_mask = cv2.bitwise_or(non_brick_material, gray_material)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    laplacian = cv2.convertScaleAbs(cv2.Laplacian(gray, cv2.CV_16S, ksize=3))
    textured = (laplacian > 13).astype(np.uint8) * 255
    candidate_mask = cv2.bitwise_and(
        candidate_mask,
        cv2.dilate(textured, cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9)), iterations=1),
    )
    candidate_mask = cv2.morphologyEx(
        candidate_mask,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_RECT, (17, 17)),
        iterations=2,
    )
    candidate_mask = cv2.morphologyEx(
        candidate_mask,
        cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7)),
        iterations=1,
    )

    contours, _ = cv2.findContours(candidate_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    candidates: list[tuple[float, tuple[int, int, int, int]]] = []

    for contour in contours:
        x, y, box_w, box_h = cv2.boundingRect(contour)
        area = box_w * box_h
        aspect = box_w / max(1, box_h)
        contour_area = cv2.contourArea(contour)

        if area < width * height * 0.0022 or area > width * height * 0.16:
            continue
        if box_w < 32 or box_h < 30:
            continue
        if aspect < 0.45 or aspect > 3.8:
            continue

        fill_ratio = contour_area / max(1, area)
        if fill_ratio < 0.12:
            continue

        roi_hsv = hsv[y : y + box_h, x : x + box_w]
        blue_ratio = (
            (roi_hsv[:, :, 0] >= 78)
            & (roi_hsv[:, :, 0] <= 125)
            & (roi_hsv[:, :, 1] > 45)
            & (roi_hsv[:, :, 2] > 80)
        ).mean()
        if blue_ratio > 0.06:
            continue

        pad = max(14, int(max(box_w, box_h) * 0.35))
        ring_x1, ring_y1 = max(0, x - pad), max(0, y - pad)
        ring_x2, ring_y2 = min(width, x + box_w + pad), min(height, y + box_h + pad)
        ring = region_mask[ring_y1:ring_y2, ring_x1:ring_x2].copy()
        ring[
            max(0, y - ring_y1) : min(ring_y2, y + box_h) - ring_y1,
            max(0, x - ring_x1) : min(ring_x2, x + box_w) - ring_x1,
        ] = 0
        ring_ratio = cv2.countNonZero(ring) / max(1, ring.size)
        ring_threshold = 0.10 if area > width * height * 0.02 else 0.18
        if ring_ratio < ring_threshold:
            continue

        center_x, center_y = x + box_w / 2, y + box_h / 2
        inside_region = False
        margin_ok = False
        for x1, y1, x2, y2, _ in brick_regions:
            if x1 - 35 <= center_x <= x2 + 35 and y1 - 35 <= center_y <= y2 + 35:
                inside_region = True
                margin_ok = center_x - x1 > 18 and x2 - center_x > 18 and center_y - y1 > 18 and y2 - center_y > 18
                break
        if not inside_region or not margin_ok:
            continue

        if area < width * height * 0.02 and _side_hits(region_mask, x, y, box_w, box_h, pad) < 2:
            continue

        box_pad = max(8, int(0.08 * max(box_w, box_h)))
        mapped_box = (
            int(max(0, x - box_pad) / scale),
            int(max(0, y - box_pad) / scale),
            int(min(width - 1, x + box_w + box_pad) / scale),
            int(min(height - 1, y + box_h + box_pad) / scale),
        )
        score = area * ring_ratio * fill_ratio
        candidates.append((score, mapped_box))

    kept: list[tuple[int, int, int, int]] = []
    for _, box in sorted(candidates, reverse=True):
        if all(_iou(box, other) < 0.25 for other in kept):
            kept.append(box)
    return kept[:4]


def _side_hits(mask: np.ndarray, x: int, y: int, width: int, height: int, pad: int) -> int:
    image_height, image_width = mask.shape[:2]
    strips = [
        (max(0, y - pad), y, max(0, x - pad), min(image_width, x + width + pad)),
        (y + height, min(image_height, y + height + pad), max(0, x - pad), min(image_width, x + width + pad)),
        (max(0, y - pad), min(image_height, y + height + pad), max(0, x - pad), x),
        (max(0, y - pad), min(image_height, y + height + pad), x + width, min(image_width, x + width + pad)),
    ]
    hits = 0
    for y1, y2, x1, x2 in strips:
        if y2 <= y1 or x2 <= x1:
            continue
        strip = mask[y1:y2, x1:x2]
        if cv2.countNonZero(strip) / max(1, strip.size) > 0.12:
            hits += 1
    return hits


def _iou(box_a: tuple[int, int, int, int], box_b: tuple[int, int, int, int]) -> float:
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    intersection = max(0, ix2 - ix1) * max(0, iy2 - iy1)
    area_a = max(1, (ax2 - ax1) * (ay2 - ay1))
    area_b = max(1, (bx2 - bx1) * (by2 - by1))
    return intersection / (area_a + area_b - intersection)


def write_yolo_label(path: Path, boxes: list[tuple[int, int, int, int]], image_shape: tuple[int, int, int]) -> None:
    height, width = image_shape[:2]
    lines = []
    for x1, y1, x2, y2 in boxes:
        x1, x2 = sorted((max(0, x1), min(width - 1, x2)))
        y1, y2 = sorted((max(0, y1), min(height - 1, y2)))
        box_w = max(1, x2 - x1)
        box_h = max(1, y2 - y1)
        x_center = (x1 + x2) / 2 / width
        y_center = (y1 + y2) / 2 / height
        lines.append(f"0 {x_center:.6f} {y_center:.6f} {box_w / width:.6f} {box_h / height:.6f}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def image_files(source: Path) -> list[Path]:
    return [path for path in sorted(source.rglob("*"), key=lambda item: str(item).lower()) if path.suffix.lower() in IMAGE_SUFFIXES]


def video_files(source: Path) -> list[Path]:
    files = [
        path
        for path in sorted(source.rglob("*"), key=lambda item: str(item).lower())
        if path.suffix.lower() in VIDEO_SUFFIXES and not path.stem.lower().endswith("_t")
    ]
    seen: set[tuple[str, int]] = set()
    unique: list[Path] = []
    for path in files:
        key = (path.name.lower(), path.stat().st_size)
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


def split_name(index: int, total: int, val_ratio: float) -> str:
    if total <= 1:
        return "train"
    return "val" if index % max(2, round(1 / max(0.05, val_ratio))) == 0 else "train"


def save_sample(
    image: np.ndarray,
    boxes: list[tuple[int, int, int, int]],
    output: Path,
    split: str,
    stem: str,
    source: str,
) -> Sample:
    image_path = output / "images" / split / f"{stem}.jpg"
    label_path = output / "labels" / split / f"{stem}.txt"
    imwrite_unicode(image_path, image)
    write_yolo_label(label_path, boxes, image.shape)
    return Sample(image_path=image_path, label_path=label_path, boxes=boxes, source=source)


def prepare_images(source: Path, output: Path, image_size: int, val_ratio: float) -> list[Sample]:
    samples: list[Sample] = []
    paths = image_files(source)
    for index, path in enumerate(paths):
        image = imread_unicode(path)
        if image is None:
            continue
        image = resize_long_side(image, image_size)
        boxes = facade_damage_boxes(image)
        split = split_name(index, len(paths), val_ratio)
        samples.append(save_sample(image, boxes, output, split, f"photo_{index:04d}_{path.stem}", str(path)))
    return samples


def iter_video_frames(
    path: Path,
    step_sec: float,
    max_frames: int,
) -> Iterable[tuple[int, np.ndarray]]:
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        return
    try:
        fps = capture.get(cv2.CAP_PROP_FPS) or 25.0
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        step = max(1, int(round(fps * step_sec)))
        indices = list(range(0, frame_count, step)) if frame_count > 0 else []
        if max_frames > 0 and len(indices) > max_frames:
            stride = len(indices) / max_frames
            indices = [indices[int(i * stride)] for i in range(max_frames)]
        for frame_index in indices:
            capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
            ok, frame = capture.read()
            if ok and frame is not None:
                yield frame_index, frame
    finally:
        capture.release()


def prepare_videos(
    source: Path,
    output: Path,
    image_size: int,
    step_sec: float,
    max_frames: int,
    max_negative_frames: int,
    val_ratio: float,
) -> list[Sample]:
    samples: list[Sample] = []
    negatives_saved = 0
    videos = video_files(source)
    global_index = 0
    for video_index, video in enumerate(videos):
        for frame_index, frame in iter_video_frames(video, step_sec, max_frames):
            image = resize_long_side(frame, image_size)
            boxes = facade_damage_boxes(image)
            if not boxes:
                if negatives_saved >= max_negative_frames:
                    continue
                negatives_saved += 1
            split = split_name(global_index, max(1, max_frames * len(videos)), val_ratio)
            stem = f"video_{video_index:02d}_{video.stem}_{frame_index:07d}"
            samples.append(save_sample(image, boxes, output, split, stem, f"{video}#{frame_index}"))
            global_index += 1
    return samples


def write_data_yaml(output: Path) -> None:
    yaml = "\n".join(
        [
            f"path: {output.as_posix()}",
            "train: images/train",
            "val: images/val",
            "names:",
            f"  0: {CLASS_NAME}",
            "",
        ]
    )
    (output / "data.yaml").write_text(yaml, encoding="utf-8")


def write_preview(samples: list[Sample], output: Path, seed: int) -> None:
    rng = random.Random(seed)
    chosen = list(samples)
    rng.shuffle(chosen)
    chosen = chosen[:40]
    tiles = []
    for sample in chosen:
        image = imread_unicode(sample.image_path)
        if image is None:
            continue
        for x1, y1, x2, y2 in sample.boxes:
            cv2.rectangle(image, (x1, y1), (x2, y2), (0, 180, 255), 3)
        height, width = image.shape[:2]
        tile_w, tile_h = 320, 180
        scale = min(tile_w / width, tile_h / height)
        resized = cv2.resize(image, (round(width * scale), round(height * scale)), interpolation=cv2.INTER_AREA)
        tile = np.full((tile_h + 34, tile_w, 3), 245, np.uint8)
        y = (tile_h - resized.shape[0]) // 2
        x = (tile_w - resized.shape[1]) // 2
        tile[y : y + resized.shape[0], x : x + resized.shape[1]] = resized
        cv2.putText(
            tile,
            f"{sample.image_path.stem[-18:]} boxes={len(sample.boxes)}",
            (8, tile_h + 22),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (20, 20, 20),
            1,
            cv2.LINE_AA,
        )
        tiles.append(tile)
    if not tiles:
        return
    cols = 5
    rows = (len(tiles) + cols - 1) // cols
    sheet = np.full((rows * tiles[0].shape[0], cols * tiles[0].shape[1], 3), 235, np.uint8)
    for index, tile in enumerate(tiles):
        row, col = divmod(index, cols)
        y = row * tile.shape[0]
        x = col * tile.shape[1]
        sheet[y : y + tile.shape[0], x : x + tile.shape[1]] = tile
    imwrite_unicode(output / "label_preview.jpg", sheet)


def write_metadata(samples: list[Sample], output: Path) -> None:
    positive = sum(1 for sample in samples if sample.boxes)
    labels = sum(len(sample.boxes) for sample in samples)
    metadata = {
        "class_name": CLASS_NAME,
        "samples": len(samples),
        "positive_samples": positive,
        "negative_samples": len(samples) - positive,
        "labels": labels,
        "sources": [
            {
                "image": str(sample.image_path),
                "label": str(sample.label_path),
                "boxes": len(sample.boxes),
                "source": sample.source,
            }
            for sample in samples
        ],
    }
    (output / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    args = parse_args()
    if not args.source.exists():
        raise FileNotFoundError(f"Source data directory not found: {args.source}")
    if args.clean and args.output.exists():
        shutil.rmtree(args.output)

    for split in ("train", "val"):
        (args.output / "images" / split).mkdir(parents=True, exist_ok=True)
        (args.output / "labels" / split).mkdir(parents=True, exist_ok=True)

    samples = prepare_images(args.source, args.output, args.image_size, args.val_ratio)
    samples.extend(
        prepare_videos(
            args.source,
            args.output,
            args.image_size,
            args.video_step_sec,
            args.max_video_frames,
            args.max_negative_video_frames,
            args.val_ratio,
        )
    )
    write_data_yaml(args.output)
    write_metadata(samples, args.output)
    write_preview(samples, args.output, args.seed)

    positives = sum(1 for sample in samples if sample.boxes)
    print(f"dataset={args.output}")
    print(f"samples={len(samples)} positives={positives} negatives={len(samples) - positives}")
    print(f"labels={sum(len(sample.boxes) for sample in samples)}")
    print(f"yaml={args.output / 'data.yaml'}")
    print(f"preview={args.output / 'label_preview.jpg'}")


if __name__ == "__main__":
    main()
