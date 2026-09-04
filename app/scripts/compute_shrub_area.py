#!/usr/bin/env python3
"""Compute shrub projected area from preclassified point CSV data."""

from __future__ import annotations

import argparse
import json
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


def connected_components(cells: set[tuple[int, int]], minimum_cells: int) -> list[int]:
    remaining = set(cells)
    sizes: list[int] = []
    neighbors = tuple((dx, dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1) if dx or dy)
    while remaining:
        start = remaining.pop()
        queue = deque([start])
        size = 1
        while queue:
            x, y = queue.popleft()
            for dx, dy in neighbors:
                candidate = (x + dx, y + dy)
                if candidate in remaining:
                    remaining.remove(candidate)
                    queue.append(candidate)
                    size += 1
        if size >= minimum_cells:
            sizes.append(size)
    return sorted(sizes, reverse=True)


def draw_overview(path: Path, points: np.ndarray) -> None:
    width, height, margin = 1280, 760, 28
    image = Image.new("RGB", (width, height), (246, 248, 251))
    draw = ImageDraw.Draw(image)
    if points.size:
        x, y = points[:, 0], points[:, 1]
        x0, x1, y0, y1 = float(x.min()), float(x.max()), float(y.min()), float(y.max())
        step = max(1, points.shape[0] // 180_000)
        for px, py in points[::step, :2]:
            sx = margin + int((px - x0) / max(x1 - x0, 1e-9) * (width - margin * 2))
            sy = height - margin - int((py - y0) / max(y1 - y0, 1e-9) * (height - margin * 2))
            draw.point((sx, sy), fill=(34, 197, 94))
    image.save(path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--resolution", type=float, default=0.25)
    parser.add_argument("--minimum-area", type=float, default=0.5)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    points = np.loadtxt(args.input, delimiter=",", skiprows=1, dtype=np.float64)
    if points.size == 0:
        points = np.empty((0, 4), dtype=np.float64)
    elif points.ndim == 1:
        points = points.reshape(1, -1)
    cells = set(zip(
        np.floor(points[:, 0] / args.resolution).astype(np.int64),
        np.floor(points[:, 1] / args.resolution).astype(np.int64),
    ))
    minimum_cells = max(1, int(np.ceil(args.minimum_area / (args.resolution ** 2))))
    patches = connected_components(cells, minimum_cells)
    patch_areas = [size * args.resolution ** 2 for size in patches]
    summary = {
        "point_count": int(points.shape[0]),
        "occupied_cells": len(cells),
        "resolution_m": args.resolution,
        "area_m2": round(len(cells) * args.resolution ** 2, 2),
        "patch_count": len(patches),
        "largest_patch_m2": round(max(patch_areas, default=0.0), 2),
        "mean_height_m": round(float(points[:, 3].mean()), 2) if points.size else 0.0,
        "method": "classification-4 occupied XY grid",
    }
    (args.output_dir / "shrub_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    draw_overview(args.output_dir / "shrub_overview.png", points)
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
