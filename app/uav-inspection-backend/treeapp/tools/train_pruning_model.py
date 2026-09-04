from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import torch
from ultralytics import YOLO


BACKEND_DIR = Path(__file__).resolve().parents[2]
TREE_APP_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DATA = TREE_APP_DIR / "pruning_dataset" / "data.yaml"
DEFAULT_BASE_MODEL = TREE_APP_DIR / "tree-pruning-best.pt"
FALLBACK_BASE_MODEL = BACKEND_DIR / "yolo11n.pt"
DEFAULT_PROJECT = TREE_APP_DIR / "runs"
DEFAULT_INSTALL = TREE_APP_DIR / "tree-pruning-best.pt"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train and install the tree pruning YOLO model.")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--model", type=Path, default=DEFAULT_BASE_MODEL)
    parser.add_argument("--epochs", type=int, default=80)
    parser.add_argument("--imgsz", type=int, default=960)
    parser.add_argument("--batch", type=int, default=4)
    parser.add_argument("--project", type=Path, default=DEFAULT_PROJECT)
    parser.add_argument("--name", default="tree_pruning_relabel")
    parser.add_argument("--install", type=Path, default=DEFAULT_INSTALL)
    parser.add_argument("--backup", action="store_true", help="Back up the install target before replacing it.")
    return parser.parse_args()


def choose_base_model(requested: Path) -> Path:
    if requested.exists():
        return requested
    if FALLBACK_BASE_MODEL.exists():
        return FALLBACK_BASE_MODEL
    raise FileNotFoundError(f"Base model not found: {requested} or {FALLBACK_BASE_MODEL}")


def main() -> None:
    args = parse_args()
    if not args.data.exists():
        raise FileNotFoundError(f"Dataset yaml not found: {args.data}")

    base_model = choose_base_model(args.model)
    device = 0 if torch.cuda.is_available() else "cpu"
    model = YOLO(str(base_model))
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
        patience=18,
        close_mosaic=8,
        mosaic=0.25,
        scale=0.12,
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
        backup_path = args.install.with_name(f"{args.install.stem}.backup{args.install.suffix}")
        shutil.copy2(args.install, backup_path)
        print(f"backup={backup_path}")

    shutil.copy2(best, args.install)
    print(f"base_model={base_model}")
    print(f"best={best}")
    print(f"installed={args.install}")


if __name__ == "__main__":
    main()
