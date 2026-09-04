from __future__ import annotations

import argparse
import csv
import json
import random
import re
import shutil
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path


DEFAULT_WORKSPACE = Path(r"C:\Users\DL-X17R2\Desktop\无人机数据\外墙\annotation_workspace")
CLASS_NAMES = ["Crack", "Seepage", "TileSpalling", "Hollowing"]


@dataclass(frozen=True)
class Sample:
    image: Path
    label: Path
    group: str
    class_counts: Counter[int]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a combined visible-light facade dataset.")
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    parser.add_argument("--output-name", default="dataset_v2")
    parser.add_argument("--val-ratio", type=float, default=0.2)
    parser.add_argument("--chunk-sec", type=float, default=20.0)
    parser.add_argument("--seed", type=int, default=20260714)
    parser.add_argument("--clean", action="store_true")
    return parser.parse_args()


def load_manifest(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return {row["image"].lower(): row for row in csv.DictReader(stream)}


def canonical_video_source(source: str) -> str:
    normalized = Path(source).stem.lower()
    aliases = {
        "dji_20260402154807_0001_v": "visible_q1",
        "q1": "visible_q1",
        "dji_20260402154854_0002_v": "visible_q2",
        "q2": "visible_q2",
        "dji_20260408104054_0001_v": "visible_main",
        "q3": "visible_main",
        "dji_20260408104946_0002_v": "visible_short",
    }
    return aliases.get(normalized, normalized)


def group_for(row: dict[str, str], fallback_name: str, chunk_sec: float) -> str:
    kind = row.get("kind", "")
    source = row.get("source", fallback_name)
    if kind != "video":
        return f"photo:{Path(source).stem.lower()}"
    canonical = canonical_video_source(source)
    time_sec = float(row.get("time_sec") or 0)
    chunk = int(time_sec // chunk_sec)
    return f"video:{canonical}:chunk_{chunk:04d}"


def validate_label(path: Path) -> Counter[int]:
    counts: Counter[int] = Counter()
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) != 5:
            raise ValueError(f"{path}:{line_number}: expected 5 values")
        class_id = int(parts[0])
        values = [float(value) for value in parts[1:]]
        if class_id not in range(len(CLASS_NAMES)):
            raise ValueError(f"{path}:{line_number}: invalid class {class_id}")
        if any(value < 0 or value > 1 for value in values) or values[2] <= 0 or values[3] <= 0:
            raise ValueError(f"{path}:{line_number}: invalid coordinates")
        counts[class_id] += 1
    return counts


def collect_samples(workspace: Path, chunk_sec: float) -> list[Sample]:
    old_manifest = load_manifest(workspace / "reports" / "prepared_manifest.csv")
    round2_manifest = load_manifest(workspace / "reports" / "round2_visible_manifest.csv")
    sources = [
        (
            workspace / "images" / "to_label",
            workspace / "labels" / "to_label",
            old_manifest,
            None,
        ),
        (
            workspace / "images" / "round2_visible",
            workspace / "labels" / "round2_visible",
            round2_manifest,
            {path.name.lower() for path in (workspace / "images" / "round2_batches" / "batch_01").glob("*.jpg")},
        ),
    ]
    samples: list[Sample] = []

    for image_dir, label_dir, manifest, allowed_names in sources:
        image_by_stem = {path.stem.lower(): path for path in image_dir.glob("*.jpg")}
        for label in sorted(label_dir.glob("*.txt")):
            image = image_by_stem.get(label.stem.lower())
            if image is None:
                continue
            if allowed_names is not None and image.name.lower() not in allowed_names:
                continue
            row = manifest.get(image.name.lower(), {})
            samples.append(Sample(
                image=image,
                label=label,
                group=group_for(row, image.name, chunk_sec),
                class_counts=validate_label(label),
            ))
    return samples


def choose_val_groups(samples: list[Sample], ratio: float, seed: int) -> set[str]:
    grouped: dict[str, list[Sample]] = defaultdict(list)
    for sample in samples:
        grouped[sample.group].append(sample)
    groups = sorted(grouped)
    target = max(1, round(len(samples) * ratio))
    present_classes = {class_id for sample in samples for class_id in sample.class_counts}

    for attempt in range(2000):
        shuffled = groups[:]
        random.Random(seed + attempt).shuffle(shuffled)
        selected: set[str] = set()
        selected_count = 0
        for group in shuffled:
            if selected_count >= target:
                break
            selected.add(group)
            selected_count += len(grouped[group])
        val_classes = {class_id for group in selected for sample in grouped[group] for class_id in sample.class_counts}
        train_classes = {
            class_id
            for group in groups
            if group not in selected
            for sample in grouped[group]
            for class_id in sample.class_counts
        }
        if present_classes <= val_classes and present_classes <= train_classes:
            return selected
    raise RuntimeError("Unable to create train/val split containing every annotated class")


def main() -> None:
    args = parse_args()
    workspace = args.workspace.resolve()
    output = workspace / args.output_name
    samples = collect_samples(workspace, args.chunk_sec)
    if not samples:
        raise RuntimeError("No labeled samples found")
    val_groups = choose_val_groups(samples, args.val_ratio, args.seed)

    if args.clean:
        shutil.rmtree(output, ignore_errors=True)
    split_counts: Counter[str] = Counter()
    split_classes: dict[str, Counter[int]] = {"train": Counter(), "val": Counter()}
    split_groups: dict[str, set[str]] = {"train": set(), "val": set()}

    for sample in samples:
        split = "val" if sample.group in val_groups else "train"
        image_target = output / "images" / split / sample.image.name
        label_target = output / "labels" / split / f"{sample.image.stem}.txt"
        image_target.parent.mkdir(parents=True, exist_ok=True)
        label_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(sample.image, image_target)
        shutil.copy2(sample.label, label_target)
        split_counts[split] += 1
        split_classes[split].update(sample.class_counts)
        split_groups[split].add(sample.group)

    yaml_path = output / "data.yaml"
    yaml_path.write_text("\n".join([
        f"path: {output.as_posix()}",
        "train: images/train",
        "val: images/val",
        "names:",
        *[f"  {index}: {name}" for index, name in enumerate(CLASS_NAMES)],
        "",
    ]), encoding="utf-8")

    report = {
        "total_images": len(samples),
        "train_images": split_counts["train"],
        "val_images": split_counts["val"],
        "train_groups": sorted(split_groups["train"]),
        "val_groups": sorted(split_groups["val"]),
        "group_overlap": sorted(split_groups["train"] & split_groups["val"]),
        "train_class_counts": {CLASS_NAMES[index]: split_classes["train"][index] for index in range(len(CLASS_NAMES))},
        "val_class_counts": {CLASS_NAMES[index]: split_classes["val"][index] for index in range(len(CLASS_NAMES))},
    }
    report_path = workspace / "reports" / f"{args.output_name}_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"data={yaml_path}")
    print(f"report={report_path}")


if __name__ == "__main__":
    main()
