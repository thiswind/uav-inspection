from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO


BACKEND_DIR = Path(__file__).resolve().parents[2]
HEATMAP_APP_DIR = Path(__file__).resolve().parents[1]
DEFAULT_VIDEOS = [
    BACKEND_DIR / "heatmapdata" / "videos" / "1.MP4",
    BACKEND_DIR / "heatmapdata" / "videos" / "2.mp4",
    BACKEND_DIR / "heatmapdata" / "videos" / "3.mp4",
]
DEFAULT_MODEL = BACKEND_DIR / "heatmapweight" / "renliu.pt"
DEFAULT_OUTPUT = HEATMAP_APP_DIR / "demo_person_dataset"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare a fixed-video aerial person YOLO dataset.")
    parser.add_argument("--videos", nargs="*", type=Path, default=DEFAULT_VIDEOS)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--frame-step", type=int, default=45, help="Extract one training frame every N video frames.")
    parser.add_argument("--max-frames-per-video", type=int, default=80)
    parser.add_argument("--max-side", type=int, default=1280)
    parser.add_argument("--predict-imgsz", type=int, default=1280)
    parser.add_argument("--predict-conf", type=float, default=0.08)
    parser.add_argument("--min-label-conf", type=float, default=0.12)
    parser.add_argument("--preview-count", type=int, default=16)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def resize_keep_aspect(frame: np.ndarray, max_side: int) -> np.ndarray:
    height, width = frame.shape[:2]
    longest = max(width, height)
    if longest <= max_side:
        return frame
    scale = max_side / longest
    return cv2.resize(frame, (round(width * scale), round(height * scale)), interpolation=cv2.INTER_AREA)


def valid_person_box(
    box: np.ndarray,
    confidence: float,
    image_width: int,
    image_height: int,
    min_confidence: float,
) -> bool:
    x1, y1, x2, y2 = [float(v) for v in box]
    width = max(0.0, x2 - x1)
    height = max(0.0, y2 - y1)
    if confidence < min_confidence or width <= 0 or height <= 0:
        return False

    # The demo videos are top-down 4K drone clips. Real pedestrians are small,
    # compact boxes; large plant beds and tree crowns are the dominant false positives.
    scale_x = image_width / 3840.0
    scale_y = image_height / 2160.0
    min_w = max(5.0, 14.0 * scale_x)
    min_h = max(5.0, 14.0 * scale_y)
    max_w = max(36.0, 130.0 * scale_x)
    max_h = max(36.0, 130.0 * scale_y)
    min_area = max(24.0, 180.0 * scale_x * scale_y)
    max_area = max(900.0, 11000.0 * scale_x * scale_y)
    aspect = width / max(height, 1.0)

    return (
        min_w <= width <= max_w
        and min_h <= height <= max_h
        and min_area <= width * height <= max_area
        and 0.35 <= aspect <= 2.0
    )


def yolo_line(box: np.ndarray, width: int, height: int) -> str:
    x1, y1, x2, y2 = [float(v) for v in box]
    cx = ((x1 + x2) / 2.0) / width
    cy = ((y1 + y2) / 2.0) / height
    bw = (x2 - x1) / width
    bh = (y2 - y1) / height
    return f"0 {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}"


def draw_preview(frame: np.ndarray, boxes: list[tuple[np.ndarray, float]], caption: str) -> np.ndarray:
    preview = frame.copy()
    for box, confidence in boxes:
        x1, y1, x2, y2 = [int(round(v)) for v in box]
        cv2.rectangle(preview, (x1, y1), (x2, y2), (0, 230, 255), 2)
        cv2.putText(
            preview,
            f"person {confidence:.2f}",
            (x1, max(18, y1 - 4)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (0, 230, 255),
            1,
            cv2.LINE_AA,
        )
    cv2.putText(preview, caption, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.85, (0, 255, 0), 2, cv2.LINE_AA)
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
        cv2.copyMakeBorder(item, 0, max_h - item.shape[0], 0, 0, cv2.BORDER_CONSTANT, value=(25, 25, 25))
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


def collect_video_frames(
    model: YOLO,
    video_path: Path,
    args: argparse.Namespace,
    images_dir: Path,
    labels_dir: Path,
    start_index: int,
    previews: list[np.ndarray],
) -> tuple[int, int, int]:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    saved = 0
    total_boxes = 0
    frame_idx = 0

    while frame_idx < total_frames and saved < args.max_frames_per_video:
        ok, frame = cap.read()
        if not ok:
            break
        if frame_idx % max(args.frame_step, 1) != 0:
            frame_idx += 1
            continue

        frame = resize_keep_aspect(frame, args.max_side)
        height, width = frame.shape[:2]
        result = model.predict(
            frame,
            conf=args.predict_conf,
            iou=0.45,
            imgsz=args.predict_imgsz,
            classes=[0],
            verbose=False,
            max_det=220,
        )[0]

        boxes: list[tuple[np.ndarray, float]] = []
        if result.boxes is not None:
            xyxy = result.boxes.xyxy.cpu().numpy()
            confs = result.boxes.conf.cpu().numpy()
            for box, confidence in zip(xyxy, confs):
                if valid_person_box(box, float(confidence), width, height, args.min_label_conf):
                    boxes.append((box, float(confidence)))

        if boxes:
            stem = f"{video_path.stem.lower()}_{start_index + saved:04d}_f{frame_idx:06d}"
            image_path = images_dir / f"{stem}.jpg"
            label_path = labels_dir / f"{stem}.txt"
            cv2.imwrite(str(image_path), frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
            label_path.write_text("\n".join(yolo_line(box, width, height) for box, _ in boxes) + "\n", encoding="utf-8")

            if len(previews) < args.preview_count:
                caption = f"{video_path.name}  f{frame_idx}  t={frame_idx / fps:.1f}s  people={len(boxes)}"
                previews.append(draw_preview(frame, boxes, caption))

            saved += 1
            total_boxes += len(boxes)

        frame_idx += 1

    cap.release()
    return saved, total_boxes, start_index + saved


def main() -> None:
    args = parse_args()
    missing = [path for path in args.videos if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing video(s): " + ", ".join(str(path) for path in missing))
    if not args.model.exists():
        raise FileNotFoundError(f"Labeling model not found: {args.model}")
    if args.output.exists() and not args.overwrite:
        raise FileExistsError(f"Output already exists, pass --overwrite: {args.output}")
    if args.output.exists() and args.overwrite:
        shutil.rmtree(args.output)

    images_dir = args.output / "images" / "train"
    labels_dir = args.output / "labels" / "train"
    images_dir.mkdir(parents=True, exist_ok=True)
    labels_dir.mkdir(parents=True, exist_ok=True)

    model = YOLO(str(args.model))
    previews: list[np.ndarray] = []
    total_images = 0
    total_boxes = 0
    next_index = 0

    for video_path in args.videos:
        saved, boxes, next_index = collect_video_frames(
            model, video_path, args, images_dir, labels_dir, next_index, previews
        )
        total_images += saved
        total_boxes += boxes
        print(f"{video_path.name}: frames_saved={saved} boxes={boxes}")

    data_yaml = args.output / "data.yaml"
    data_yaml.write_text(
        "\n".join(
            [
                f"path: {args.output.as_posix()}",
                "train: images/train",
                "val: images/train",
                "nc: 1",
                "names:",
                "  0: person",
                "",
            ]
        ),
        encoding="utf-8",
    )
    make_contact_sheet(previews, args.output / "preview_labels.jpg")

    print(f"output={args.output}")
    print(f"frames_saved={total_images}")
    print(f"boxes={total_boxes}")
    print(f"data={data_yaml}")
    print(f"preview={args.output / 'preview_labels.jpg'}")


if __name__ == "__main__":
    main()
