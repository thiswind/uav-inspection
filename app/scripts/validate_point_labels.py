#!/usr/bin/env python3
"""Read-only validation for CloudCompare point-label exports."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont


CLASSES = ("tree", "car", "shrub")
CLASS_COLORS = {
    "background": (145, 151, 163),
    "tree": (22, 163, 74),
    "car": (37, 99, 235),
    "shrub": (217, 70, 239),
}
INSTANCE_COLORS = (
    (239, 68, 68), (249, 115, 22), (234, 179, 8), (132, 204, 22),
    (34, 197, 94), (20, 184, 166), (6, 182, 212), (59, 130, 246),
    (99, 102, 241), (168, 85, 247), (217, 70, 239), (244, 63, 94),
)


@dataclass
class InstanceStats:
    count: int = 0
    xyz_min: list[float] = field(default_factory=lambda: [math.inf] * 3)
    xyz_max: list[float] = field(default_factory=lambda: [-math.inf] * 3)
    xyz_sum: list[float] = field(default_factory=lambda: [0.0] * 3)
    z_sample: list[float] = field(default_factory=list)

    def add(self, xyz: tuple[float, float, float], rng: random.Random, limit: int) -> None:
        self.count += 1
        for index, value in enumerate(xyz):
            self.xyz_min[index] = min(self.xyz_min[index], value)
            self.xyz_max[index] = max(self.xyz_max[index], value)
            self.xyz_sum[index] += value
        if len(self.z_sample) < limit:
            self.z_sample.append(xyz[2])
        else:
            replace = rng.randrange(self.count)
            if replace < limit:
                self.z_sample[replace] = xyz[2]


def update_sample(samples, seen, key, point, rng, limit):
    seen[key] += 1
    bucket = samples[key]
    if len(bucket) < limit:
        bucket.append(point)
        return
    replace = rng.randrange(seen[key])
    if replace < limit:
        bucket[replace] = point


def parse_label(token: bytes):
    text = token.decode("ascii", errors="replace").strip().lower()
    if text == "nan":
        return None, None
    try:
        value = float(text)
    except ValueError:
        return None, f"not numeric: {text}"
    if not math.isfinite(value) or value <= 0 or not value.is_integer():
        return None, f"not a positive integer: {text}"
    return int(value), None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb", buffering=16 * 1024 * 1024) as stream:
        while chunk := stream.read(16 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def draw_panel(draw, rect, points, bounds, projection, color_mode, title):
    left, top, right, bottom = rect
    draw.rounded_rectangle(rect, radius=18, fill=(248, 250, 252), outline=(203, 213, 225), width=2)
    draw.text((left + 18, top + 14), title, fill=(15, 23, 42))
    plot_left, plot_top = left + 20, top + 52
    plot_right, plot_bottom = right - 20, bottom - 35
    axes = projection
    lo0, hi0 = bounds[axes[0]]
    lo1, hi1 = bounds[axes[1]]
    span0 = max(hi0 - lo0, 1e-9)
    span1 = max(hi1 - lo1, 1e-9)
    for key, bucket in points.items():
        if color_mode == "semantic":
            semantic = key.split(":", 1)[0]
            color = CLASS_COLORS[semantic]
        else:
            semantic, raw_id = key.split(":", 1)
            if semantic != "tree":
                continue
            color = INSTANCE_COLORS[(int(raw_id) - 1) % len(INSTANCE_COLORS)]
        for x, y, z in bucket:
            values = (x, y, z)
            px = plot_left + int((values[axes[0]] - lo0) / span0 * (plot_right - plot_left))
            py = plot_bottom - int((values[axes[1]] - lo1) / span1 * (plot_bottom - plot_top))
            draw.point((px, py), fill=color)
    draw.text((plot_left, plot_bottom + 8), f"{('XYZ'[axes[0]])}: {lo0:.2f} – {hi0:.2f}", fill=(71, 85, 105))
    draw.text((plot_right - 190, plot_bottom + 8), f"{('XYZ'[axes[1]])}: {lo1:.2f} – {hi1:.2f}", fill=(71, 85, 105))


def create_overview(path, samples, bounds, color_mode):
    image = Image.new("RGB", (1600, 820), "white")
    draw = ImageDraw.Draw(image)
    heading = "Point-label validation: semantic classes" if color_mode == "semantic" else "Point-label validation: tree instances"
    draw.text((28, 18), heading, fill=(15, 23, 42))
    draw_panel(draw, (25, 60, 790, 790), samples, bounds, (0, 1), color_mode, "Top view (X/Y)")
    draw_panel(draw, (810, 60, 1575, 790), samples, bounds, (0, 2), color_mode, "Side view (X/Z)")
    if color_mode == "semantic":
        x = 1130
        for label in ("background", "tree", "car", "shrub"):
            draw.rectangle((x, 24, x + 14, 38), fill=CLASS_COLORS[label])
            draw.text((x + 20, 22), label, fill=(51, 65, 85))
            x += 108
    image.save(path)


def create_tree_contact_sheet(path, samples, instance_rows):
    tree_rows = [row for row in instance_rows if row["class"] == "tree"]
    columns = 2
    rows = math.ceil(len(tree_rows) / columns)
    cell_width, cell_height = 800, 285
    image = Image.new("RGB", (columns * cell_width, rows * cell_height + 45), "white")
    draw = ImageDraw.Draw(image)
    draw.text((24, 16), "Per-tree label QA (individually normalized views)", fill=(15, 23, 42))
    for position, metrics in enumerate(tree_rows):
        column, row_index = position % columns, position // columns
        left, top = column * cell_width + 15, row_index * cell_height + 45
        right, bottom = left + cell_width - 30, top + cell_height - 15
        draw.rounded_rectangle((left, top, right, bottom), radius=15, fill=(248, 250, 252), outline=(203, 213, 225), width=2)
        instance_id = int(metrics["instance_id"])
        color = INSTANCE_COLORS[(instance_id - 1) % len(INSTANCE_COLORS)]
        draw.text((left + 14, top + 10), f"Tree {instance_id}  |  {metrics['points']:,} points", fill=(15, 23, 42))
        draw.text(
            (left + 330, top + 10),
            f"XY {metrics['x_span']:.2f} x {metrics['y_span']:.2f} m  |  P99-P01 {metrics['robust_z_span_p99_p01']:.2f} m",
            fill=(71, 85, 105),
        )
        bucket = samples.get(f"tree:{instance_id}", [])
        if not bucket:
            continue
        values = np.asarray(bucket, dtype=np.float64)
        panels = ((0, 1, left + 15, "Top X/Y"), (0, 2, left + 395, "Side X/Z"))
        for axis0, axis1, panel_left, title in panels:
            panel_top, panel_right, panel_bottom = top + 48, panel_left + 355, bottom - 20
            draw.rectangle((panel_left, panel_top, panel_right, panel_bottom), fill="white", outline=(226, 232, 240))
            draw.text((panel_left + 7, panel_top + 5), title, fill=(100, 116, 139))
            lo0, hi0 = float(values[:, axis0].min()), float(values[:, axis0].max())
            lo1, hi1 = float(values[:, axis1].min()), float(values[:, axis1].max())
            span0, span1 = max(hi0 - lo0, 1e-9), max(hi1 - lo1, 1e-9)
            for point in values:
                px = panel_left + 8 + int((point[axis0] - lo0) / span0 * (panel_right - panel_left - 16))
                py = panel_bottom - 8 - int((point[axis1] - lo1) / span1 * (panel_bottom - panel_top - 24))
                draw.point((px, py), fill=color)
    image.save(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--txt", required=True, type=Path)
    parser.add_argument("--bin", dest="bin_path", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--plot-samples", type=int, default=5000)
    parser.add_argument("--quantile-samples", type=int, default=200000)
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    rng = random.Random(20260715)
    global_min = [math.inf] * 3
    global_max = [-math.inf] * 3
    instances = {name: defaultdict(InstanceStats) for name in CLASSES}
    class_points = Counter()
    samples = defaultdict(list)
    sample_seen = Counter()
    row_count = invalid_rows = unlabeled = multi_label = 0
    nonfinite_xyz = rgb_out_of_range = malformed_labels = 0
    header = ""

    txt_digest = hashlib.sha256()
    with args.txt.open("rb", buffering=16 * 1024 * 1024) as stream:
        header_bytes = stream.readline()
        txt_digest.update(header_bytes)
        header = header_bytes.decode("utf-8", errors="replace").strip()
        for line in stream:
            txt_digest.update(line)
            parts = line.split()
            if len(parts) != 9:
                invalid_rows += 1
                continue
            try:
                xyz = tuple(float(value) for value in parts[:3])
                rgb = tuple(int(value) for value in parts[3:6])
            except ValueError:
                invalid_rows += 1
                continue
            row_count += 1
            if not all(math.isfinite(value) for value in xyz):
                nonfinite_xyz += 1
                continue
            if not all(0 <= value <= 255 for value in rgb):
                rgb_out_of_range += 1
            for index, value in enumerate(xyz):
                global_min[index] = min(global_min[index], value)
                global_max[index] = max(global_max[index], value)

            active = []
            row_bad_label = False
            for class_name, token in zip(CLASSES, parts[6:9]):
                instance_id, error = parse_label(token)
                if error:
                    malformed_labels += 1
                    row_bad_label = True
                elif instance_id is not None:
                    active.append((class_name, instance_id))
                    class_points[class_name] += 1
                    instances[class_name][instance_id].add(xyz, rng, args.quantile_samples)
            if not active:
                unlabeled += 1
                sample_key = "background:0"
            else:
                if len(active) > 1:
                    multi_label += 1
                sample_key = f"{active[0][0]}:{active[0][1]}"
            if not row_bad_label:
                update_sample(samples, sample_seen, sample_key, xyz, rng, args.plot_samples)

    with args.bin_path.open("rb") as stream:
        bin_magic = stream.read(4).decode("ascii", errors="replace")

    bounds = list(zip(global_min, global_max))
    instance_rows = []
    for class_name in CLASSES:
        for instance_id, stats in sorted(instances[class_name].items()):
            z_values = np.asarray(stats.z_sample, dtype=np.float64)
            percentiles = np.percentile(z_values, [1, 5, 50, 95, 99]) if z_values.size else [math.nan] * 5
            row = {
                "class": class_name,
                "instance_id": instance_id,
                "points": stats.count,
                "x_min": stats.xyz_min[0], "x_max": stats.xyz_max[0],
                "y_min": stats.xyz_min[1], "y_max": stats.xyz_max[1],
                "z_min": stats.xyz_min[2], "z_max": stats.xyz_max[2],
                "x_span": stats.xyz_max[0] - stats.xyz_min[0],
                "y_span": stats.xyz_max[1] - stats.xyz_min[1],
                "z_span": stats.xyz_max[2] - stats.xyz_min[2],
                "z_p01": float(percentiles[0]), "z_p05": float(percentiles[1]),
                "z_p50": float(percentiles[2]), "z_p95": float(percentiles[3]),
                "z_p99": float(percentiles[4]),
                "robust_z_span_p99_p01": float(percentiles[4] - percentiles[0]),
                "centroid_x": stats.xyz_sum[0] / stats.count,
                "centroid_y": stats.xyz_sum[1] / stats.count,
                "centroid_z": stats.xyz_sum[2] / stats.count,
            }
            instance_rows.append(row)

    total_label_assignments = sum(class_points.values())
    errors = []
    warnings = []
    if bin_magic != "CCB2": errors.append(f"Unexpected BIN magic: {bin_magic!r}")
    if invalid_rows: errors.append(f"Malformed row count: {invalid_rows}")
    if nonfinite_xyz: errors.append(f"Non-finite XYZ row count: {nonfinite_xyz}")
    if malformed_labels: errors.append(f"Malformed label value count: {malformed_labels}")
    if multi_label: errors.append(f"Conflicting multi-label row count: {multi_label}")
    if rgb_out_of_range: warnings.append(f"RGB out-of-range row count: {rgb_out_of_range}")
    if row_count and unlabeled / row_count > 0.5:
        warnings.append(f"Background/unlabeled points are {unlabeled / row_count:.1%} of all points; they mix unknown classes.")
    for class_name in CLASSES:
        count = len(instances[class_name])
        if count < 20:
            warnings.append(f"{class_name} has only {count} instances; insufficient for a generalizable instance model.")
    tree_counts = [item["points"] for item in instance_rows if item["class"] == "tree"]
    if tree_counts and max(tree_counts) / min(tree_counts) > 20:
        warnings.append(f"Tree instance point counts are highly imbalanced ({max(tree_counts) / min(tree_counts):.1f}:1 max/min).")
    warnings.append("No explicit ground or lawn label is present; tree-height ground elevation and green-area training need separate data.")

    summary = {
        "inputs": {
            "txt": str(args.txt), "txt_bytes": args.txt.stat().st_size,
            "txt_sha256": txt_digest.hexdigest(),
            "bin": str(args.bin_path), "bin_bytes": args.bin_path.stat().st_size,
            "bin_sha256": sha256_file(args.bin_path), "bin_magic": bin_magic,
        },
        "schema": header,
        "rows": row_count,
        "invalid_rows": invalid_rows,
        "nonfinite_xyz_rows": nonfinite_xyz,
        "rgb_out_of_range_rows": rgb_out_of_range,
        "malformed_label_values": malformed_labels,
        "multi_label_rows": multi_label,
        "unlabeled_points": unlabeled,
        "unlabeled_ratio": unlabeled / row_count if row_count else None,
        "labeled_assignments": total_label_assignments,
        "bounds": {axis: {"min": lo, "max": hi, "span": hi - lo} for axis, (lo, hi) in zip("XYZ", bounds)},
        "classes": {
            name: {"points": class_points[name], "ratio": class_points[name] / row_count, "instances": len(instances[name])}
            for name in CLASSES
        },
        "errors": errors,
        "warnings": warnings,
        "verdict": "PASS_WITH_WARNINGS" if not errors else "FAIL",
    }

    (args.output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    with (args.output / "instance_metrics.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(instance_rows[0]))
        writer.writeheader()
        writer.writerows(instance_rows)

    create_overview(args.output / "semantic_overview.png", samples, bounds, "semantic")
    create_overview(args.output / "tree_instances_overview.png", samples, bounds, "instance")
    create_tree_contact_sheet(args.output / "tree_instance_contact_sheet.png", samples, instance_rows)

    class_lines = "\n".join(
        f"| {name} | {class_points[name]:,} | {class_points[name] / row_count:.2%} | {len(instances[name])} |"
        for name in CLASSES
    )
    tree_lines = "\n".join(
        f"| {row['instance_id']} | {row['points']:,} | {row['x_span']:.2f} | {row['y_span']:.2f} | {row['robust_z_span_p99_p01']:.2f} | {row['z_min']:.2f}–{row['z_max']:.2f} |"
        for row in instance_rows if row["class"] == "tree"
    )
    issue_lines = "\n".join(f"- {value}" for value in errors + warnings)
    report = f"""# 当前三维点云标注验证报告

## 结论

验证状态：`{summary['verdict']}`。文件结构完整、可解析；详细限制见“问题与风险”。

## 文件与结构

- TXT 行数：{row_count:,}
- BIN 文件头：`{bin_magic}`
- 无效数据行：{invalid_rows:,}
- 冲突多标签点：{multi_label:,}
- 未标注点：{unlabeled:,}（{unlabeled / row_count:.2%}）
- 坐标跨度：X {bounds[0][1] - bounds[0][0]:.2f} m，Y {bounds[1][1] - bounds[1][0]:.2f} m，Z {bounds[2][1] - bounds[2][0]:.2f} m

## 类别统计

| 类别 | 点数 | 占全部点 | 实例数 |
|---|---:|---:|---:|
{class_lines}

## 树木实例统计

`P99-P01` 是标签点的稳健垂直跨度，仅用于标注质检，不等同于最终树高。

| 树ID | 点数 | X跨度(m) | Y跨度(m) | P99-P01(m) | 完整Z范围(m) |
|---:|---:|---:|---:|---:|---:|
{tree_lines}

## 问题与风险

{issue_lines}

## 生成文件

- `summary.json`：机器可读总体统计
- `instance_metrics.csv`：逐实例统计
- `semantic_overview.png`：语义标签抽样俯视图/侧视图
- `tree_instances_overview.png`：树木实例抽样俯视图/侧视图
- `tree_instance_contact_sheet.png`：逐棵树独立归一化质检图
"""
    (args.output / "validation_report.md").write_text(report, encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
