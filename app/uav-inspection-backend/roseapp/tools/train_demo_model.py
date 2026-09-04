from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import torch
from ultralytics import YOLO


ROSE_APP_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DATA = ROSE_APP_DIR / "demo_dataset" / "data.yaml"
DEFAULT_BASE_MODEL = ROSE_APP_DIR / "rose-detect-best.pt"
DEFAULT_PROJECT = ROSE_APP_DIR / "runs"
DEFAULT_INSTALL = ROSE_APP_DIR / "rose-detect-best.pt"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train the fixed-video rose demo model.")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--model", type=Path, default=DEFAULT_BASE_MODEL)
    parser.add_argument("--epochs", type=int, default=80)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--project", type=Path, default=DEFAULT_PROJECT)
    parser.add_argument("--name", default="rose_demo_fixed")
    parser.add_argument("--install", type=Path, default=DEFAULT_INSTALL)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.data.exists():
        raise FileNotFoundError(f"Dataset yaml not found: {args.data}")
    if not args.model.exists():
        raise FileNotFoundError(f"Base model not found: {args.model}")

    device = 0 if torch.cuda.is_available() else "cpu"
    model = YOLO(str(args.model))
    result = model.train(
        data=str(args.data),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=device,
        project=str(args.project),
        name=args.name,
        exist_ok=True,
        workers=2,
        cache=False,
        single_cls=False,
        pretrained=True,
        patience=20,
        close_mosaic=8,
        mosaic=0.2,
        scale=0.1,
        translate=0.03,
        fliplr=0.0,
        plots=True,
    )

    save_dir = Path(result.save_dir)
    best = save_dir / "weights" / "best.pt"
    if not best.exists():
        raise FileNotFoundError(f"Training finished but best.pt was not found: {best}")

    args.install.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(best, args.install)
    print(f"best={best}")
    print(f"installed={args.install}")


if __name__ == "__main__":
    main()
