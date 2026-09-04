from __future__ import annotations

import argparse
import csv
import shutil
import sys
from pathlib import Path

import cv2
import numpy as np


BACKEND_DIR = Path(__file__).resolve().parents[2]
TREE_APP_DIR = Path(__file__).resolve().parents[1]
MEDIA_DIR = BACKEND_DIR / "treedata" / "media"
DEFAULT_OUTPUT = TREE_APP_DIR / "pruning_dataset"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from treeapp.detector import CLASS_NAMES, tree_pruning_detector  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Extract frames from pruning videos, create YOLO pre-labels with the current "
            "model, and write a review manifest for manual relabeling."
        )
    )
    parser.add_argument("--video", action="append", dest="videos", type=Path, help="Video path. Can be passed multiple times.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--frame-step", type=int, default=30, help="Extract one frame every N frames.")
    parser.add_argument("--max-side", type=int, default=960)
    parser.add_argument("--max-frames", type=int, default=220, help="Safety cap across all input videos. Use 0 for no cap.")
    parser.add_argument("--conf", type=float, default=0.18, help="Low threshold for pre-label recall. Review labels before training.")
    parser.add_argument("--iou", type=float, default=0.45)
    parser.add_argument("--val-every", type=int, default=5, help="Every Nth saved frame goes to val.")
    parser.add_argument("--positive-only", action="store_true", help="Skip frames without model boxes.")
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def collect_default_videos() -> list[Path]:
    if not MEDIA_DIR.exists():
        return []
    videos = []
    for item in MEDIA_DIR.iterdir():
        name = item.name.lower()
        if item.suffix.lower() != ".mp4":
            continue
        if "source" in name or name.startswith("_transcode_probe"):
            continue
        videos.append(item)
    return sorted(videos)


def resize_keep_aspect(frame: np.ndarray, max_side: int) -> np.ndarray:
    height, width = frame.shape[:2]
    longest = max(width, height)
    if longest <= max_side:
        return frame
    scale = max_side / longest
    return cv2.resize(frame, (round(width * scale), round(height * scale)), interpolation=cv2.INTER_AREA)


def clamp_box(box: list[float], width: int, height: int) -> tuple[float, float, float, float] | None:
    x1, y1, x2, y2 = box
    x1 = max(0.0, min(float(width - 1), x1))
    y1 = max(0.0, min(float(height - 1), y1))
    x2 = max(0.0, min(float(width - 1), x2))
    y2 = max(0.0, min(float(height - 1), y2))
    if x2 <= x1 + 1 or y2 <= y1 + 1:
        return None
    return x1, y1, x2, y2


def yolo_line(detection: dict[str, object], width: int, height: int) -> str | None:
    class_id = int(detection["class"])
    box = clamp_box(list(detection["bbox"]), width, height)
    if box is None:
        return None
    x1, y1, x2, y2 = box
    cx = ((x1 + x2) / 2) / width
    cy = ((y1 + y2) / 2) / height
    bw = (x2 - x1) / width
    bh = (y2 - y1) / height
    return f"{class_id} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}"


def draw_preview(frame: np.ndarray, detections: list[dict[str, object]], assessment: dict[str, object], caption: str) -> np.ndarray:
    preview = frame.copy()
    colors = {
        "Pruned": (34, 197, 94),
        "PrunedTree": (16, 185, 129),
        "Unpruned": (239, 68, 68),
    }
    for item in detections:
        box = clamp_box(list(item["bbox"]), preview.shape[1], preview.shape[0])
        if box is None:
            continue
        x1, y1, x2, y2 = [int(v) for v in box]
        name = str(item.get("name", ""))
        color = colors.get(name, (56, 189, 248))
        cv2.rectangle(preview, (x1, y1), (x2, y2), color, 2)
        cv2.putText(
            preview,
            f"{name} {float(item.get('conf', 0.0)):.2f}",
            (x1, max(14, y1 - 4)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            color,
            1,
            cv2.LINE_AA,
        )

    decision = "PRUNE" if assessment.get("needs_pruning") else "OK"
    cv2.putText(preview, f"{caption}  {decision} {float(assessment.get('score', 0.0)):.2f}", (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2, cv2.LINE_AA)
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


def write_data_yaml(output: Path) -> Path:
    data_yaml = output / "data.yaml"
    lines = [
        f"path: {output.as_posix()}",
        "train: images/train",
        "val: images/val",
        f"nc: {len(CLASS_NAMES)}",
        "names:",
    ]
    for class_id in sorted(CLASS_NAMES):
        lines.append(f"  {class_id}: {CLASS_NAMES[class_id]}")
    lines.append("")
    data_yaml.write_text("\n".join(lines), encoding="utf-8")
    return data_yaml


def main() -> None:
    args = parse_args()
    videos = args.videos or collect_default_videos()
    if not videos:
        raise FileNotFoundError(f"No pruning videos found. Pass --video or add mp4 files under {MEDIA_DIR}")
    for video in videos:
        if not video.exists():
            raise FileNotFoundError(f"Video not found: {video}")

    if args.output.exists() and not args.overwrite:
        raise FileExistsError(f"Output already exists, pass --overwrite: {args.output}")
    if args.output.exists() and args.overwrite:
        shutil.rmtree(args.output)

    for split in ("train", "val"):
        (args.output / "images" / split).mkdir(parents=True, exist_ok=True)
        (args.output / "labels" / split).mkdir(parents=True, exist_ok=True)

    manifest_path = args.output / "review_manifest.csv"
    previews: list[np.ndarray] = []
    saved = 0
    boxes_total = 0

    with manifest_path.open("w", newline="", encoding="utf-8") as manifest_file:
        writer = csv.DictWriter(
            manifest_file,
            fieldnames=[
                "split",
                "image",
                "label",
                "video",
                "frame_index",
                "time_sec",
                "box_count",
                "needs_pruning",
                "score",
                "branch_score",
                "leaf_score",
                "yellow_leaf_score",
                "reasons",
            ],
        )
        writer.writeheader()

        for video in videos:
            cap = cv2.VideoCapture(str(video))
            if not cap.isOpened():
                raise RuntimeError(f"Cannot open video: {video}")
            fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)

            for frame_index in range(frame_count):
                ok, frame = cap.read()
                if not ok:
                    break
                if frame_index % max(args.frame_step, 1) != 0:
                    continue
                if args.max_frames and saved >= args.max_frames:
                    break

                frame = resize_keep_aspect(frame, args.max_side)
                result = tree_pruning_detector.detect(frame, conf_threshold=args.conf, iou_threshold=args.iou)
                detections = result["detections"]
                if args.positive_only and not detections:
                    continue

                split = "val" if args.val_every > 0 and saved % args.val_every == 0 else "train"
                stem = f"{video.stem}_{saved:05d}_f{frame_index:07d}"
                image_path = args.output / "images" / split / f"{stem}.jpg"
                label_path = args.output / "labels" / split / f"{stem}.txt"

                cv2.imwrite(str(image_path), frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
                height, width = frame.shape[:2]
                lines = [line for item in detections if (line := yolo_line(item, width, height))]
                label_path.write_text(("\n".join(lines) + "\n") if lines else "", encoding="utf-8")

                assessment = result["pruning_assessment"]
                features = assessment["features"]
                writer.writerow(
                    {
                        "split": split,
                        "image": image_path.relative_to(args.output).as_posix(),
                        "label": label_path.relative_to(args.output).as_posix(),
                        "video": str(video),
                        "frame_index": frame_index,
                        "time_sec": round(frame_index / fps, 3) if fps else "",
                        "box_count": len(detections),
                        "needs_pruning": assessment["needs_pruning"],
                        "score": assessment["score"],
                        "branch_score": features["branch_score"],
                        "leaf_score": features["leaf_score"],
                        "yellow_leaf_score": features["yellow_leaf_score"],
                        "reasons": " | ".join(assessment["reasons"]),
                    }
                )

                if len(previews) < 16:
                    caption = f"{video.stem} {frame_index / fps:.1f}s" if fps else f"{video.stem} f{frame_index}"
                    previews.append(draw_preview(frame, detections, assessment, caption))

                boxes_total += len(detections)
                saved += 1

            cap.release()
            if args.max_frames and saved >= args.max_frames:
                break

    data_yaml = write_data_yaml(args.output)
    preview_path = args.output / "preview_prelabels.jpg"
    make_contact_sheet(previews, preview_path)

    print(f"videos={len(videos)}")
    print(f"frames_saved={saved}")
    print(f"boxes={boxes_total}")
    print(f"dataset={args.output}")
    print(f"data={data_yaml}")
    print(f"review_manifest={manifest_path}")
    print(f"preview={preview_path}")
    print("Review and correct labels before training; the generated boxes are pre-labels, not ground truth.")


if __name__ == "__main__":
    main()
