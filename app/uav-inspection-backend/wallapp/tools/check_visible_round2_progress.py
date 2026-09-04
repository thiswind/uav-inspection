from __future__ import annotations

import argparse
from pathlib import Path


DEFAULT_WORKSPACE = Path(r"C:\Users\DL-X17R2\Desktop\无人机数据\外墙\annotation_workspace")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check round-two visible-light annotation progress.")
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    workspace = args.workspace.resolve()
    batch_root = workspace / "images" / "round2_batches"
    label_dir = workspace / "labels" / "round2_visible"
    label_stems = {path.stem.lower() for path in label_dir.glob("*.txt")}
    total_images = 0
    total_reviewed = 0

    for batch_dir in sorted(path for path in batch_root.iterdir() if path.is_dir()):
        images = sorted(batch_dir.glob("*.jpg"))
        reviewed = sum(image.stem.lower() in label_stems for image in images)
        total_images += len(images)
        total_reviewed += reviewed
        print(f"{batch_dir.name}: reviewed={reviewed}/{len(images)}, remaining={len(images) - reviewed}")

    print(f"total: reviewed={total_reviewed}/{total_images}, remaining={total_images - total_reviewed}")
    print(f"labels={label_dir}")


if __name__ == "__main__":
    main()
