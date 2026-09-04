#!/usr/bin/env python3
"""Create conservative tree instance candidates from preclassified tree points."""

from __future__ import annotations

import argparse
import csv
import colorsys
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


def select_peaks(x, y, hag, grid_size, min_height, min_distance):
    x0, y0 = float(x.min()), float(y.min())
    ix = np.floor((x - x0) / grid_size).astype(np.int32)
    iy = np.floor((y - y0) / grid_size).astype(np.int32)
    nx, ny = int(ix.max()) + 1, int(iy.max()) + 1
    heights = np.full(nx * ny, -np.inf, dtype=np.float32)
    np.maximum.at(heights, ix * ny + iy, hag.astype(np.float32))
    occupied = np.flatnonzero(heights >= min_height)
    order = occupied[np.argsort(heights[occupied])[::-1]]
    radius_cells = max(1, int(math.ceil(min_distance / grid_size)))
    blocked = np.zeros((nx, ny), dtype=bool)
    peaks = []
    for flat in order:
        gx, gy = divmod(int(flat), ny)
        if blocked[gx, gy]:
            continue
        peaks.append((x0 + (gx + 0.5) * grid_size, y0 + (gy + 0.5) * grid_size, float(heights[flat])))
        xa, xb = max(0, gx - radius_cells), min(nx, gx + radius_cells + 1)
        ya, yb = max(0, gy - radius_cells), min(ny, gy + radius_cells + 1)
        xx, yy = np.ogrid[xa:xb, ya:yb]
        blocked[xa:xb, ya:yb] |= (xx - gx) ** 2 + (yy - gy) ** 2 <= radius_cells ** 2
    return np.asarray(peaks, dtype=np.float64)


def assign_nearest(x, y, peaks, max_radius, chunk_size=None):
    labels = np.zeros(x.size, dtype=np.int32)
    max_distance_sq = max_radius * max_radius
    if chunk_size is None:
        # Keep the temporary distance matrices bounded for large sites.
        chunk_size = min(250_000, max(5_000, 5_000_000 // max(1, peaks.shape[0])))
    for start in range(0, x.size, chunk_size):
        stop = min(x.size, start + chunk_size)
        dx = x[start:stop, None] - peaks[None, :, 0]
        dy = y[start:stop, None] - peaks[None, :, 1]
        distances = dx * dx + dy * dy
        nearest = np.argmin(distances, axis=1)
        best = distances[np.arange(stop - start), nearest]
        labels[start:stop] = np.where(best <= max_distance_sq, nearest + 1, 0)
    return labels


def palette(instance_id):
    hue = (instance_id * 0.61803398875) % 1.0
    r, g, b = colorsys.hsv_to_rgb(hue, 0.82, 0.95)
    return int(r * 255), int(g * 255), int(b * 255)


def write_ply(path, data, labels):
    valid = labels > 0
    selected = data[valid]
    selected_labels = labels[valid]
    dtype = np.dtype([
        ("x", "<f8"), ("y", "<f8"), ("z", "<f8"),
        ("red", "u1"), ("green", "u1"), ("blue", "u1"),
        ("tree_id", "<i4"), ("height_above_ground", "<f4"),
    ])
    output = np.empty(selected.shape[0], dtype=dtype)
    output["x"], output["y"], output["z"] = selected[:, 0], selected[:, 1], selected[:, 2]
    output["tree_id"] = selected_labels
    output["height_above_ground"] = selected[:, 6].astype(np.float32)
    colors = np.asarray([palette(int(value)) for value in selected_labels], dtype=np.uint8)
    output["red"], output["green"], output["blue"] = colors[:, 0], colors[:, 1], colors[:, 2]
    header = (
        "ply\nformat binary_little_endian 1.0\n"
        "comment Generated conservative tree instance prelabels\n"
        f"element vertex {output.shape[0]}\n"
        "property double x\nproperty double y\nproperty double z\n"
        "property uchar red\nproperty uchar green\nproperty uchar blue\n"
        "property int tree_id\nproperty float height_above_ground\nend_header\n"
    ).encode("ascii")
    with path.open("wb") as stream:
        stream.write(header)
        output.tofile(stream)


def write_overview(path, x, y, labels):
    width, height, margin = 1400, 1000, 30
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    x0, x1, y0, y1 = float(x.min()), float(x.max()), float(y.min()), float(y.max())
    step = max(1, x.size // 180_000)
    for px, py, label in zip(x[::step], y[::step], labels[::step]):
        if label <= 0:
            continue
        sx = margin + int((px - x0) / max(x1 - x0, 1e-9) * (width - 2 * margin))
        sy = height - margin - int((py - y0) / max(y1 - y0, 1e-9) * (height - 2 * margin))
        draw.point((sx, sy), fill=palette(int(label)))
    image.save(path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--grid-size", type=float, default=0.25)
    parser.add_argument("--min-height", type=float, default=2.5)
    parser.add_argument("--min-distance", type=float, default=4.0)
    parser.add_argument("--max-radius", type=float, default=8.0)
    parser.add_argument("--min-points", type=int, default=500)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    data = np.loadtxt(args.input, delimiter=",", skiprows=1, dtype=np.float64)
    if data.ndim != 2 or data.shape[1] != 7:
        raise ValueError(f"Expected 7 columns, got {data.shape}")
    peaks = select_peaks(data[:, 0], data[:, 1], data[:, 6], args.grid_size, args.min_height, args.min_distance)
    labels = assign_nearest(data[:, 0], data[:, 1], peaks, args.max_radius)

    counts = np.bincount(labels, minlength=peaks.shape[0] + 1)
    keep = np.flatnonzero(counts >= args.min_points)
    keep = keep[keep > 0]
    remap = np.zeros(peaks.shape[0] + 1, dtype=np.int32)
    remap[keep] = np.arange(1, keep.size + 1)
    labels = remap[labels]

    write_ply(args.output_dir / "tree_instances_colored.ply", data, labels)
    write_overview(args.output_dir / "tree_instances_overview.png", data[:, 0], data[:, 1], labels)

    rows = []
    for tree_id in range(1, int(labels.max()) + 1):
        subset = data[labels == tree_id]
        rows.append({
            "tree_id": tree_id,
            "points": int(subset.shape[0]),
            "x_min": float(subset[:, 0].min()), "x_max": float(subset[:, 0].max()),
            "y_min": float(subset[:, 1].min()), "y_max": float(subset[:, 1].max()),
            "z_min": float(subset[:, 2].min()), "z_max": float(subset[:, 2].max()),
            "height_p99": float(np.percentile(subset[:, 6], 99)),
            "centroid_x": float(subset[:, 0].mean()), "centroid_y": float(subset[:, 1].mean()),
        })
    with (args.output_dir / "tree_instances.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]) if rows else ["tree_id", "points"])
        writer.writeheader()
        writer.writerows(rows)
    summary = {
        "source_points": int(data.shape[0]),
        "candidate_peaks": int(peaks.shape[0]),
        "retained_instances": len(rows),
        "assigned_points": int(np.count_nonzero(labels)),
        "unassigned_points": int(np.count_nonzero(labels == 0)),
        "parameters": vars(args) | {"input": str(args.input), "output_dir": str(args.output_dir)},
    }
    (args.output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
