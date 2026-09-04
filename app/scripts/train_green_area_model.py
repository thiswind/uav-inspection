#!/usr/bin/env python3
"""Self-label WebODM orthophotos and train a green-cover area model."""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


TASK_NAMES = {
    "task_01_xinxixueyuan_1": "信息学院1号地",
    "task_02_xinxixueyuan_2": "信息学院2号地",
    "task_03_meiguiyuan_2": "玫瑰园2号地",
    "task_04_meiguiyuan_1": "玫瑰园1号地",
    "task_05_meiguiyuan_3": "玫瑰园3号地",
}
CLASS_NAMES = ("other", "green")
FEATURE_NAMES = (
    "red_ratio",
    "green_ratio",
    "blue_ratio",
    "excess_green",
    "ngrdi",
    "green_blue_index",
    "brightness",
    "saturation",
)
MODEL_VERSION = "green_area_gnb_v1"


@dataclass
class TaskSamples:
    key: str
    image_size: tuple[int, int]
    label_size: tuple[int, int]
    pixel_size: tuple[float, float]
    features: np.ndarray
    labels: np.ndarray
    available: dict[str, int]
    sampled: dict[str, int]


@dataclass
class GaussianNB:
    means: np.ndarray
    variances: np.ndarray
    priors: np.ndarray

    @classmethod
    def fit(cls, features: np.ndarray, labels: np.ndarray) -> "GaussianNB":
        means = []
        variances = []
        priors = []
        for class_id in range(len(CLASS_NAMES)):
            values = features[labels == class_id].astype(np.float64, copy=False)
            if values.size == 0:
                raise ValueError(f"class {CLASS_NAMES[class_id]} has no samples")
            means.append(values.mean(axis=0))
            variances.append(np.maximum(values.var(axis=0), 1e-6))
            priors.append(values.shape[0] / features.shape[0])
        return cls(np.asarray(means), np.asarray(variances), np.asarray(priors))

    def log_proba(self, features: np.ndarray) -> np.ndarray:
        values = features.astype(np.float64, copy=False)
        scores = []
        for class_id in range(len(CLASS_NAMES)):
            variance = self.variances[class_id]
            score = -0.5 * np.sum(
                np.log(2 * math.pi * variance) + ((values - self.means[class_id]) ** 2) / variance,
                axis=1,
            )
            scores.append(score + math.log(max(self.priors[class_id], 1e-12)))
        return np.column_stack(scores)

    def predict(self, features: np.ndarray) -> np.ndarray:
        return np.argmax(self.log_proba(features), axis=1).astype(np.uint8)

    def green_probability(self, features: np.ndarray) -> np.ndarray:
        scores = self.log_proba(features)
        difference = np.clip(scores[:, 1] - scores[:, 0], -50, 50)
        return (1.0 / (1.0 + np.exp(-difference))).astype(np.float32)


def rgb_features(rgb: np.ndarray) -> np.ndarray:
    values = rgb.astype(np.float32) / 255.0
    red, green, blue = values[..., 0], values[..., 1], values[..., 2]
    total = red + green + blue + 1e-6
    red_ratio = red / total
    green_ratio = green / total
    blue_ratio = blue / total
    excess_green = 2.0 * green_ratio - red_ratio - blue_ratio
    ngrdi = (green - red) / (green + red + 1e-6)
    green_blue_index = (green - blue) / (green + blue + 1e-6)
    maximum = values.max(axis=-1)
    minimum = values.min(axis=-1)
    saturation = (maximum - minimum) / (maximum + 1e-6)
    brightness = values.mean(axis=-1)
    return np.stack(
        (
            red_ratio,
            green_ratio,
            blue_ratio,
            excess_green,
            ngrdi,
            green_blue_index,
            brightness,
            saturation,
        ),
        axis=-1,
    )


def confident_labels(rgba: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    features = rgb_features(rgba[..., :3])
    red_ratio = features[..., 0]
    green_ratio = features[..., 1]
    blue_ratio = features[..., 2]
    excess_green = features[..., 3]
    brightness = features[..., 6]
    saturation = features[..., 7]
    valid = (rgba[..., 3] >= 250) & (brightness > 0.045)
    green = (
        valid
        & (brightness < 0.96)
        & (saturation > 0.10)
        & (green_ratio > red_ratio + 0.012)
        & (green_ratio > blue_ratio + 0.008)
        & (excess_green > 0.045)
    )
    other = (
        valid
        & ~green
        & (
            (excess_green < -0.015)
            | (green_ratio < red_ratio - 0.025)
            | (green_ratio < blue_ratio - 0.035)
            | (saturation < 0.045)
        )
    )
    return features, other, green


def geo_pixel_size(image: Image.Image) -> tuple[float, float]:
    scale = image.tag_v2.get(33550)
    if not scale or len(scale) < 2:
        raise ValueError("GeoTIFF is missing ModelPixelScaleTag (33550)")
    return abs(float(scale[0])), abs(float(scale[1]))


def sample_indices(indices: np.ndarray, maximum: int, rng: np.random.Generator) -> np.ndarray:
    if indices.size <= maximum:
        return indices
    return rng.choice(indices, size=maximum, replace=False)


def save_pseudolabel_preview(
    path: Path,
    rgba: np.ndarray,
    other: np.ndarray,
    green: np.ndarray,
) -> None:
    preview = np.zeros((*rgba.shape[:2], 4), dtype=np.uint8)
    valid = rgba[..., 3] >= 250
    preview[valid] = (100, 116, 139, 160)
    preview[other] = (51, 65, 85, 255)
    preview[green] = (22, 163, 74, 255)
    Image.fromarray(preview, "RGBA").save(path)


def collect_task_samples(
    image_path: Path,
    output_dir: Path,
    maximum_samples: int,
    label_max_dimension: int,
    seed: int,
) -> TaskSamples:
    key = image_path.parent.name
    with Image.open(image_path) as source:
        pixel_size = geo_pixel_size(source)
        image_size = source.size
        preview = source.convert("RGBA")
        preview.thumbnail((label_max_dimension, label_max_dimension), Image.Resampling.LANCZOS)
        rgba = np.asarray(preview)
    features, other_mask, green_mask = confident_labels(rgba)
    flat_features = features.reshape(-1, features.shape[-1])
    rng = np.random.default_rng(seed)
    class_indices = [np.flatnonzero(other_mask), np.flatnonzero(green_mask)]
    selected = [sample_indices(indices, maximum_samples, rng) for indices in class_indices]
    sampled_features = np.concatenate([flat_features[indices] for indices in selected], axis=0)
    sampled_labels = np.concatenate(
        [np.full(indices.size, class_id, dtype=np.uint8) for class_id, indices in enumerate(selected)]
    )
    order = rng.permutation(sampled_labels.size)
    save_pseudolabel_preview(output_dir / f"{key}_labels.png", rgba, other_mask, green_mask)
    return TaskSamples(
        key=key,
        image_size=image_size,
        label_size=preview.size,
        pixel_size=pixel_size,
        features=sampled_features[order],
        labels=sampled_labels[order],
        available={name: int(class_indices[index].size) for index, name in enumerate(CLASS_NAMES)},
        sampled={name: int(selected[index].size) for index, name in enumerate(CLASS_NAMES)},
    )


def metrics_from_confusion(confusion: np.ndarray) -> dict:
    total = int(confusion.sum())
    classes = {}
    f1_values = []
    for class_id, name in enumerate(CLASS_NAMES):
        true_positive = int(confusion[class_id, class_id])
        predicted = int(confusion[:, class_id].sum())
        support = int(confusion[class_id].sum())
        precision = true_positive / predicted if predicted else 0.0
        recall = true_positive / support if support else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        classes[name] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": support,
        }
        f1_values.append(f1)
    return {
        "accuracy": float(np.trace(confusion) / total) if total else 0.0,
        "macro_f1": float(np.mean(f1_values)),
        "classes": classes,
        "confusion_matrix": confusion.astype(int).tolist(),
    }


def evaluate(model: GaussianNB, features: np.ndarray, labels: np.ndarray) -> dict:
    predictions = model.predict(features)
    confusion = np.zeros((len(CLASS_NAMES), len(CLASS_NAMES)), dtype=np.int64)
    np.add.at(confusion, (labels, predictions), 1)
    return metrics_from_confusion(confusion)


def cross_validate(tasks: list[TaskSamples]) -> tuple[dict, list[dict]]:
    aggregate = np.zeros((len(CLASS_NAMES), len(CLASS_NAMES)), dtype=np.int64)
    folds = []
    for held_out in tasks:
        train_features = np.concatenate([task.features for task in tasks if task.key != held_out.key])
        train_labels = np.concatenate([task.labels for task in tasks if task.key != held_out.key])
        model = GaussianNB.fit(train_features, train_labels)
        fold_metrics = evaluate(model, held_out.features, held_out.labels)
        fold_confusion = np.asarray(fold_metrics["confusion_matrix"], dtype=np.int64)
        aggregate += fold_confusion
        folds.append({"held_out_task": held_out.key, **fold_metrics})
    return metrics_from_confusion(aggregate), folds


def draw_confusion_matrix(path: Path, metrics: dict) -> None:
    confusion = np.asarray(metrics["confusion_matrix"], dtype=np.int64)
    image = Image.new("RGB", (760, 650), (248, 250, 252))
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    draw.text((30, 22), "Green-area model: task-level cross-validation", fill=(15, 23, 42), font=font)
    draw.text((30, 48), "Rows: pseudo-label truth  |  Columns: prediction", fill=(71, 85, 105), font=font)
    left, top, cell = 185, 145, 220
    maximum = max(int(confusion.max()), 1)
    for index, name in enumerate(CLASS_NAMES):
        draw.text((left + index * cell + 80, top - 38), name, fill=(51, 65, 85), font=font)
        draw.text((55, top + index * cell + 100), name, fill=(51, 65, 85), font=font)
    for row in range(2):
        row_total = max(int(confusion[row].sum()), 1)
        for column in range(2):
            value = int(confusion[row, column])
            strength = value / maximum
            if row == column:
                color = (int(224 - 120 * strength), int(242 - 45 * strength), int(231 - 80 * strength))
            else:
                color = (int(254 - 20 * strength), int(226 - 80 * strength), int(226 - 80 * strength))
            x0, y0 = left + column * cell, top + row * cell
            draw.rectangle((x0, y0, x0 + cell - 8, y0 + cell - 8), fill=color, outline=(203, 213, 225), width=2)
            draw.text((x0 + 70, y0 + 78), f"{value:,}", fill=(15, 23, 42), font=font)
            draw.text((x0 + 80, y0 + 108), f"{value / row_total:.1%}", fill=(71, 85, 105), font=font)
    draw.text(
        (30, 610),
        f"Accuracy {metrics['accuracy']:.3f}  |  Macro F1 {metrics['macro_f1']:.3f}",
        fill=(15, 23, 42),
        font=font,
    )
    image.save(path)


def clean_mask(mask: np.ndarray, minimum_pixels: int) -> tuple[np.ndarray, list[int]]:
    kernel = np.ones((3, 3), dtype=np.uint8)
    cleaned = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_CLOSE, kernel)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(cleaned, connectivity=8)
    if count <= 1:
        return np.zeros_like(mask), []
    component_sizes = stats[1:, cv2.CC_STAT_AREA]
    keep_ids = np.flatnonzero(component_sizes >= minimum_pixels) + 1
    kept = np.isin(labels, keep_ids).astype(np.uint8)
    return kept, sorted((int(component_sizes[index - 1]) for index in keep_ids), reverse=True)


def save_area_preview(path: Path, image_path: Path, mask: np.ndarray) -> None:
    with Image.open(image_path) as source:
        base = source.convert("RGB")
        base.thumbnail((1600, 1000), Image.Resampling.LANCZOS)
    resized_mask = Image.fromarray(mask * 255, "L").resize(base.size, Image.Resampling.NEAREST)
    overlay = Image.new("RGBA", base.size, (22, 163, 74, 0))
    overlay.putalpha(resized_mask.point(lambda value: 150 if value else 0))
    composed = Image.alpha_composite(base.convert("RGBA"), overlay)
    draw = ImageDraw.Draw(composed)
    draw.rectangle((18, 18, 270, 58), fill=(15, 23, 42, 220))
    draw.rectangle((32, 31, 48, 47), fill=(22, 163, 74, 255))
    draw.text((60, 30), "model green-cover mask", fill="white")
    composed.convert("RGB").save(path, quality=92)


def infer_task(
    model: GaussianNB,
    image_path: Path,
    output_dir: Path,
    threshold: float,
    minimum_area: float,
    tile_rows: int,
) -> dict:
    with Image.open(image_path) as source:
        pixel_size = geo_pixel_size(source)
        rgba = np.asarray(source.convert("RGBA"))
    height, width = rgba.shape[:2]
    raw_mask = np.zeros((height, width), dtype=np.uint8)
    probability_sum = 0.0
    predicted_pixels = 0
    valid_pixels = int(np.count_nonzero(rgba[..., 3] >= 250))
    for row_start in range(0, height, tile_rows):
        row_end = min(row_start + tile_rows, height)
        tile = rgba[row_start:row_end]
        valid = tile[..., 3].reshape(-1) >= 250
        if not np.any(valid):
            continue
        features = rgb_features(tile[..., :3]).reshape(-1, len(FEATURE_NAMES))
        probabilities = model.green_probability(features[valid])
        selected = probabilities >= threshold
        tile_mask = np.zeros(valid.size, dtype=np.uint8)
        valid_indices = np.flatnonzero(valid)
        tile_mask[valid_indices[selected]] = 1
        raw_mask[row_start:row_end] = tile_mask.reshape(row_end - row_start, width)
        probability_sum += float(probabilities[selected].sum())
        predicted_pixels += int(np.count_nonzero(selected))
    pixel_area = pixel_size[0] * pixel_size[1]
    minimum_pixels = max(1, math.ceil(minimum_area / pixel_area))
    mask, components = clean_mask(raw_mask, minimum_pixels)
    green_pixels = int(np.count_nonzero(mask))
    output_dir.mkdir(parents=True, exist_ok=True)
    Image.fromarray(mask * 255, "L").save(output_dir / "green_area_mask.png")
    save_area_preview(output_dir / "green_area_overview.jpg", image_path, mask)
    summary = {
        "model": MODEL_VERSION,
        "source": str(image_path),
        "image_width": width,
        "image_height": height,
        "valid_pixels": valid_pixels,
        "green_pixels": green_pixels,
        "pixel_size_x_m": pixel_size[0],
        "pixel_size_y_m": pixel_size[1],
        "pixel_area_m2": pixel_area,
        "area_m2": round(green_pixels * pixel_area, 2),
        "valid_area_m2": round(valid_pixels * pixel_area, 2),
        "coverage_ratio": green_pixels / valid_pixels if valid_pixels else 0.0,
        "patch_count": len(components),
        "largest_patch_m2": round((components[0] if components else 0) * pixel_area, 2),
        "mean_confidence": probability_sum / predicted_pixels if predicted_pixels else 0.0,
        "probability_threshold": threshold,
        "minimum_patch_area_m2": minimum_area,
        "method": "orthophoto RGB GaussianNB segmentation with GeoTIFF pixel-area conversion",
    }
    (output_dir / "green_area_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return summary


def write_training_report(path: Path, metrics: dict, tasks: list[TaskSamples]) -> None:
    rows = "\n".join(
        f"| {TASK_NAMES.get(task.key, task.key)} | {task.sampled['other']:,} | {task.sampled['green']:,} | "
        f"{task.pixel_size[0]:.4f} x {task.pixel_size[1]:.4f} |"
        for task in tasks
    )
    class_rows = "\n".join(
        f"| {'非绿化' if name == 'other' else '绿化'} | {values['precision']:.3f} | "
        f"{values['recall']:.3f} | {values['f1']:.3f} | {values['support']:,} |"
        for name, values in metrics["validation_metrics"]["classes"].items()
    )
    report = f"""# 绿化面积像素分类模型 V1

模型：对角高斯朴素贝叶斯。输入为 WebODM RGB 正射影像的 8 个颜色派生特征，不使用绝对坐标。

## 自标注与划分

从 5 个正射任务按绿色优势、饱和度和亮度规则生成高置信伪标签；边界不确定像素不参与训练。验证采用整任务五折留出，每个任务恰好作为一次验证集，避免相邻像素随机拆分造成的数据泄漏。

| 任务 | 非绿化样本 | 绿化样本 | 像元尺寸（米） |
|---|---:|---:|---:|
{rows}

## 任务级交叉验证

- Accuracy：{metrics['validation_metrics']['accuracy']:.3f}
- Macro F1：{metrics['validation_metrics']['macro_f1']:.3f}

| 类别 | Precision | Recall | F1 | 验证像素 |
|---|---:|---:|---:|---:|
{class_rows}

## 面积计算

模型在原始分辨率正射影像上输出绿化概率，以 {metrics['inference']['probability_threshold']:.2f} 为阈值，清理小于 {metrics['inference']['minimum_patch_area_m2']:.2f} 平方米的连通噪声，再按 GeoTIFF 像元尺寸换算水平投影面积。

## 限制

标签由 RGB 规则自标注，并非现场人工测绘真值；阴影、枯黄植被、绿色屋面和密集树冠可能造成误差。当前验证衡量的是模型跨任务复现伪标签的能力，正式交付仍需抽样人工复核或 RTK 边界校验。
"""
    path.write_text(report, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    project_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--imagery-root",
        type=Path,
        default=project_root / "webodm_downloads" / "test_20260715",
    )
    parser.add_argument(
        "--model-dir", type=Path, default=project_root / "models" / MODEL_VERSION
    )
    parser.add_argument(
        "--label-dir",
        type=Path,
        default=project_root / "training_data" / "green_area_pseudolabels_v1",
    )
    parser.add_argument(
        "--measurement-root", type=Path, default=project_root / "measurement_data"
    )
    parser.add_argument("--maximum-samples-per-class", type=int, default=80_000)
    parser.add_argument("--label-max-dimension", type=int, default=1800)
    parser.add_argument("--probability-threshold", type=float, default=0.65)
    parser.add_argument("--minimum-patch-area", type=float, default=0.5)
    parser.add_argument("--tile-rows", type=int, default=256)
    parser.add_argument("--seed", type=int, default=20260719)
    parser.add_argument("--skip-inference", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    image_paths = sorted(args.imagery_root.glob("task_*/orthophoto.tif"))
    if len(image_paths) < 2:
        raise SystemExit(f"expected at least two orthophotos under {args.imagery_root}")
    args.model_dir.mkdir(parents=True, exist_ok=True)
    args.label_dir.mkdir(parents=True, exist_ok=True)

    tasks = []
    for index, image_path in enumerate(image_paths):
        print(f"[labels] {image_path.parent.name}", flush=True)
        tasks.append(
            collect_task_samples(
                image_path,
                args.label_dir,
                args.maximum_samples_per_class,
                args.label_max_dimension,
                args.seed + index,
            )
        )

    validation_metrics, folds = cross_validate(tasks)
    all_features = np.concatenate([task.features for task in tasks])
    all_labels = np.concatenate([task.labels for task in tasks])
    model = GaussianNB.fit(all_features, all_labels)
    train_metrics = evaluate(model, all_features, all_labels)
    np.savez_compressed(
        args.model_dir / "model.npz",
        means=model.means,
        variances=model.variances,
        priors=model.priors,
        feature_names=np.asarray(FEATURE_NAMES),
        class_names=np.asarray(CLASS_NAMES),
        probability_threshold=np.asarray(args.probability_threshold),
        minimum_patch_area_m2=np.asarray(args.minimum_patch_area),
    )
    browser_model = {
        "version": MODEL_VERSION,
        "feature_names": list(FEATURE_NAMES),
        "class_names": list(CLASS_NAMES),
        "means": model.means.tolist(),
        "variances": model.variances.tolist(),
        "priors": model.priors.tolist(),
        "probability_threshold": args.probability_threshold,
    }
    (args.model_dir / "model.json").write_text(
        json.dumps(browser_model, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    draw_confusion_matrix(args.model_dir / "confusion_matrix.png", validation_metrics)

    label_manifest = {
        "version": MODEL_VERSION,
        "method": "high-confidence RGB pseudo-labels",
        "classes": list(CLASS_NAMES),
        "tasks": [
            {
                "key": task.key,
                "source": str(args.imagery_root / task.key / "orthophoto.tif"),
                "image_size": list(task.image_size),
                "label_size": list(task.label_size),
                "pixel_size_m": list(task.pixel_size),
                "available": task.available,
                "sampled": task.sampled,
                "preview": f"{task.key}_labels.png",
            }
            for task in tasks
        ],
    }
    (args.label_dir / "manifest.json").write_text(
        json.dumps(label_manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    sample_counts = {
        task.key: {"available": task.available, "sampled": task.sampled} for task in tasks
    }
    metrics = {
        "model": "diagonal_gaussian_naive_bayes",
        "version": MODEL_VERSION,
        "features": list(FEATURE_NAMES),
        "source": str(args.imagery_root),
        "label_manifest": str(args.label_dir / "manifest.json"),
        "split": "five-fold leave-one-task-out",
        "sample_counts": sample_counts,
        "training_samples": int(all_labels.size),
        "validation_samples": int(all_labels.size),
        "train_metrics": train_metrics,
        "validation_metrics": validation_metrics,
        "folds": folds,
        "inference": {
            "probability_threshold": args.probability_threshold,
            "minimum_patch_area_m2": args.minimum_patch_area,
        },
    }
    results = {}
    if not args.skip_inference:
        for image_path in image_paths:
            key = image_path.parent.name
            print(f"[inference] {key}", flush=True)
            results[key] = infer_task(
                model,
                image_path,
                args.measurement_root / key,
                args.probability_threshold,
                args.minimum_patch_area,
                args.tile_rows,
            )
    metrics["task_results"] = results
    (args.model_dir / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    write_training_report(args.model_dir / "training_report.md", metrics, tasks)
    print(
        json.dumps(
            {
                "model": str(args.model_dir / "model.npz"),
                "accuracy": validation_metrics["accuracy"],
                "macro_f1": validation_metrics["macro_f1"],
                "tasks": {key: value["area_m2"] for key, value in results.items()},
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
