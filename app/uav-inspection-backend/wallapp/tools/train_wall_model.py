from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import torch
from ultralytics import YOLO


BACKEND_DIR = Path(__file__).resolve().parents[2]
WALL_APP_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DATA = WALL_APP_DIR / "wall_damage_dataset" / "data.yaml"
DEFAULT_BASE_MODEL = BACKEND_DIR / "yolo11n.pt"
DEFAULT_PROJECT = WALL_APP_DIR / "runs"
DEFAULT_INSTALL = WALL_APP_DIR / "wall-damage-best.pt"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train and install the facade damage YOLO model.")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--model", type=Path, default=DEFAULT_BASE_MODEL)
    parser.add_argument("--epochs", type=int, default=45)
    parser.add_argument("--imgsz", type=int, default=960)
    parser.add_argument("--batch", type=int, default=6)
    parser.add_argument("--project", type=Path, default=DEFAULT_PROJECT)
    parser.add_argument("--name", default="wall_damage")
    parser.add_argument("--install", type=Path, default=DEFAULT_INSTALL)
    parser.add_argument("--backup", action="store_true", help="Back up the install target before replacing it.")
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
        single_cls=True,
        pretrained=True,
        patience=10,
        close_mosaic=6,
        mosaic=0.25,
        scale=0.15,
        translate=0.04,
        fliplr=0.0,
        plots=True,
    )

    save_dir = Path(result.save_dir)
    best = save_dir / "weights" / "best.pt"
    if not best.exists():
        raise FileNotFoundError(f"Training finished but best.pt was not found: {best}")

    args.install.parent.mkdir(parents=True, exist_ok=True)
    if args.backup and args.install.exists():
        backup = args.install.with_name(f"{args.install.stem}.backup{args.install.suffix}")
        shutil.copy2(args.install, backup)
        print(f"backup={backup}")

    shutil.copy2(best, args.install)
    print(f"device={device}")
    print(f"best={best}")
    print(f"installed={args.install}")


if __name__ == "__main__":
    main()
