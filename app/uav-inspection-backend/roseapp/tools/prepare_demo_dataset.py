from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import cv2
import numpy as np


DEFAULT_VIDEO = (
    Path(__file__).resolve().parents[2]
    / "rose-tasks"
    / "mpi1iqstncao"
    / "DJI_20260411094154_0081_V.MP4"
)
DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "demo_dataset"
CLASS_NAMES = {0: "rose", 1: "picked", 2: "bud"}
CLASS_COLORS = {0: (0, 255, 180), 1: (0, 165, 255), 2: (255, 170, 0)}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare a rose YOLO dataset from the fixed demo video.")
    parser.add_argument("--video", type=Path, default=DEFAULT_VIDEO)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--frame-step", type=int, default=3, help="Extract one frame every N video frames.")
    parser.add_argument("--max-side", type=int, default=1280, help="Resize extracted frames to this maximum side.")
    parser.add_argument("--preview-count", type=int, default=12)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def resize_keep_aspect(frame: np.ndarray, max_side: int) -> np.ndarray:
    height, width = frame.shape[:2]
    longest = max(width, height)
    if longest <= max_side:
        return frame
    scale = max_side / longest
    return cv2.resize(frame, (round(width * scale), round(height * scale)), interpolation=cv2.INTER_AREA)


def magenta_mask(frame: np.ndarray) -> np.ndarray:
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    b, g, r = cv2.split(frame)

    pink = cv2.inRange(hsv, np.array([145, 85, 65]), np.array([178, 255, 255]))
    magenta_dominance = (
        (r.astype(np.int16) > 105)
        & (b.astype(np.int16) > 65)
        & (r.astype(np.int16) - g.astype(np.int16) > 38)
        & (b.astype(np.int16) - g.astype(np.int16) > 6)
    ).astype(np.uint8) * 255
    mask = cv2.bitwise_and(pink, magenta_dominance)

    kernel_small = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    kernel_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel_small, iterations=1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel_close, iterations=1)
    return cv2.dilate(mask, kernel_small, iterations=1)


def classify_box(box: tuple[int, int, int, int], mask: np.ndarray) -> int:
    x1, y1, x2, y2 = box
    width = max(1, x2 - x1)
    height = max(1, y2 - y1)
    area = width * height
    aspect = width / max(height, 1)
    crop = mask[y1:y2, x1:x2]
    magenta_ratio = cv2.countNonZero(crop) / max(area, 1)

    # Fixed-video demo labels:
    # - large saturated heads are shown as blooming flowers
    # - tiny/tight heads are shown as buds
    # - medium or less-saturated heads are reserved for picked/harvested state
    if area <= 320 or min(width, height) <= 14 or aspect < 0.45 or aspect > 2.35:
        return 2
    if area >= 850 and magenta_ratio >= 0.28:
        return 0
    return 1


def detect_magenta_roses(frame: np.ndarray) -> list[tuple[int, int, int, int, int]]:
    mask = magenta_mask(frame)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    frame_area = frame.shape[0] * frame.shape[1]
    boxes: list[tuple[int, int, int, int, int]] = []

    for contour in contours:
        area = cv2.contourArea(contour)
        if area < 32 or area > frame_area * 0.012:
            continue
        x, y, w, h = cv2.boundingRect(contour)
        if w < 4 or h < 4:
            continue
        aspect = w / max(h, 1)
        if aspect < 0.25 or aspect > 4.0:
            continue

        pad = max(2, round(max(w, h) * 0.12))
        x1 = max(0, x - pad)
        y1 = max(0, y - pad)
        x2 = min(frame.shape[1] - 1, x + w + pad)
        y2 = min(frame.shape[0] - 1, y + h + pad)
        class_id = classify_box((x1, y1, x2, y2), mask)
        boxes.append((class_id, x1, y1, x2, y2))

    boxes.sort(key=lambda item: (item[2], item[1]))
    return boxes


def yolo_line(box: tuple[int, int, int, int, int], width: int, height: int) -> str:
    class_id, x1, y1, x2, y2 = box
    cx = ((x1 + x2) / 2) / width
    cy = ((y1 + y2) / 2) / height
    bw = (x2 - x1) / width
    bh = (y2 - y1) / height
    return f"{class_id} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}"


def draw_boxes(frame: np.ndarray, boxes: list[tuple[int, int, int, int, int]], caption: str) -> np.ndarray:
    preview = frame.copy()
    for class_id, x1, y1, x2, y2 in boxes:
        color = CLASS_COLORS[class_id]
        cv2.rectangle(preview, (x1, y1), (x2, y2), color, 2)
        cv2.putText(
            preview,
            CLASS_NAMES[class_id],
            (x1, max(12, y1 - 3)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.38,
            color,
            1,
            cv2.LINE_AA,
        )
    cv2.putText(preview, caption, (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2, cv2.LINE_AA)
    return preview


def make_contact_sheet(items: list[np.ndarray], output: Path, cols: int = 4, cell_w: int = 360) -> None:
    if not items:
        return
    resized = []
    for item in items:
        height, width = item.shape[:2]
        scale = cell_w / width
        resized.append(cv2.resize(item, (cell_w, round(height * scale)), interpolation=cv2.INTER_AREA))
    max_h = max(item.shape[0] for item in resized)
    padded = [
        cv2.copyMakeBorder(item, 0, max_h - item.shape[0], 0, 0, cv2.BORDER_CONSTANT, value=(30, 30, 30))
        for item in resized
    ]
    rows = []
    for start in range(0, len(padded), cols):
        row = padded[start : start + cols]
        while len(row) < cols:
            row.append(np.zeros_like(padded[0]))
        rows.append(cv2.hconcat(row))
    output.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output), cv2.vconcat(rows))


def main() -> None:
    args = parse_args()
    if not args.video.exists():
        raise FileNotFoundError(f"Video not found: {args.video}")
    if args.output.exists() and not args.overwrite:
        raise FileExistsError(f"Output already exists, pass --overwrite: {args.output}")
    if args.output.exists() and args.overwrite:
        shutil.rmtree(args.output)

    images_dir = args.output / "images" / "train"
    labels_dir = args.output / "labels" / "train"
    images_dir.mkdir(parents=True, exist_ok=True)
    labels_dir.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(str(args.video))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {args.video}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 0
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    saved = 0
    total_boxes = 0
    class_counts = {0: 0, 1: 0, 2: 0}
    previews: list[np.ndarray] = []

    for index in range(frame_count):
        ok, frame = cap.read()
        if not ok:
            break
        if index % max(args.frame_step, 1) != 0:
            continue

        frame = resize_keep_aspect(frame, args.max_side)
        boxes = detect_magenta_roses(frame)
        if not boxes:
            continue

        stem = f"demo_{saved:04d}_f{index:06d}"
        image_path = images_dir / f"{stem}.jpg"
        label_path = labels_dir / f"{stem}.txt"
        cv2.imwrite(str(image_path), frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
        h, w = frame.shape[:2]
        label_path.write_text("\n".join(yolo_line(box, w, h) for box in boxes) + "\n", encoding="utf-8")
        for class_id, *_ in boxes:
            class_counts[class_id] += 1

        if len(previews) < args.preview_count:
            counts = {class_id: sum(1 for item in boxes if item[0] == class_id) for class_id in CLASS_NAMES}
            summary = " ".join(f"{CLASS_NAMES[class_id]}:{counts[class_id]}" for class_id in CLASS_NAMES)
            caption = f"{index / fps:.1f}s  {summary}" if fps else f"f{index}  {summary}"
            previews.append(draw_boxes(frame, boxes, caption))

        saved += 1
        total_boxes += len(boxes)

    cap.release()

    data_yaml = args.output / "data.yaml"
    data_yaml.write_text(
        "\n".join(
            [
                f"path: {args.output.as_posix()}",
                "train: images/train",
                "val: images/train",
                "nc: 3",
                "names:",
                "  0: rose",
                "  1: picked",
                "  2: bud",
                "",
            ]
        ),
        encoding="utf-8",
    )
    make_contact_sheet(previews, args.output / "preview_labels.jpg")

    print(f"video={args.video}")
    print(f"output={args.output}")
    print(f"frames_saved={saved}")
    print(f"boxes={total_boxes}")
    print("class_counts=" + ", ".join(f"{CLASS_NAMES[class_id]}:{class_counts[class_id]}" for class_id in CLASS_NAMES))
    print(f"data={data_yaml}")
    print(f"preview={args.output / 'preview_labels.jpg'}")


if __name__ == "__main__":
    main()
