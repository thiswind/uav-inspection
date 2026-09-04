"""Create a small source package and a separate, optional runtime-data package.

Only the Python standard library is required. Original files are never moved or
modified. Every build requires a new output directory; interrupted builds are
left intact for inspection rather than removed automatically.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import sys
import zipfile


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND = "uav-inspection-backend"
FRONTEND = "uav-inspection-ui"
SKIP_DIRS = {
    ".git", ".codex", ".agents", ".venv", "venv", "node_modules",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".vite",
    "dist", "build", "coverage", "runs", "training_data", "training_datasets",
    "datasets", "debug_contact_sheets", "wall_damage_dataset",
}
ROOT_FILES = {
    "README.md", "deploy.py", "setup.bat", "start.bat", "setup.sh", "start.sh",
    "start-all-local.bat", "start-backend-local.bat", "start-frontend-local.bat",
    "start-rose-backend-local.bat", ".gitignore", ".dockerignore", "Dockerfile",
    "docker-compose.yml", "compose.yml", "pyproject.toml",
}
UI_CONFIG_FILES = {
    "package.json", "package-lock.json", "index.html", "README.md", ".gitignore",
}
TEXT_SOURCE_SUFFIXES = {
    ".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".vue", ".css",
    ".scss", ".sass", ".less", ".html", ".json", ".yaml", ".yml", ".txt",
    ".md", ".toml", ".ini", ".cfg", ".sh", ".bat", ".ps1",
}
UI_ASSET_SUFFIXES = {
    ".svg", ".png", ".jpg", ".jpeg", ".webp", ".gif", ".ico", ".woff",
    ".woff2", ".ttf", ".otf",
}
ACTIVE_WEIGHTS = (
    "heatmapweight/renliu.pt", "roseapp/rose-detect-best.pt",
    "telecomapp/station2-best.pt", "powerapp/wire-pole-seg.pt",
    "treeapp/tree-pruning-best.pt", "wallapp/wall-damage-best.pt",
)
RUNTIME_DIRS = (
    "heatmapdata/videos", "heatmapdata/snapshots", "heatmapdata/logs",
    "pestdata", "powerdata", "roofdata", "telecomdata", "treedata",
    "walldata/media", "walldata/logs", "walldata/reports", "rose-tasks",
    "telecom-tasks",
)
DATA_ASSET_SUFFIXES = {".csv", ".json", ".png", ".jpg", ".jpeg"}
DATA_README = """# 可选运行数据包

本文件夹包含运行用的视频、字幕、模型和已有分析结果，不包含 Python/npm
第三方依赖。没有本数据包也能安装和启动程序；相关任务显示为空，缺少模型的
真实 AI 检测会明确提示。首次安装程序需要联网下载依赖，不是离线安装包。

## 放置与补充数据

保持两个文件夹同级，保留数据包内部的原始子目录：

```text
部署目录/
├── 01-app/
│   ├── setup.bat
│   ├── start.bat
│   └── deployment-layout.json
└── 02-data/
    ├── uav-inspection-backend/
    ├── uav-inspection-ui/public/（rose-pictures、images）
    ├── measurement_data/
    ├── prelabel_output/instances_20260715/
    ├── models/
    └── prediction_output/
```

`uav-inspection-ui/public/images` 中的底图和瓦片是保留的离线素材备份，
当前界面未使用这些文件，地图使用外部地图服务；无需额外配置静态文件挂载。

若程序已经生成空的 02-data，把收到的数据合并进去，再重启程序。
已有上传文件与新数据重名时先备份、核对，不要直接覆盖。
不要把数据目录放进 01-app，也不要把目录中的文件全部摊平。
如要存到其他磁盘，在 01-app 内使用 `python deploy.py start --data-dir "D:/uav-data"`，
或设置 UAV_DATA_DIR；自定义目录仍须保留上述内部结构。

真实模型检测还需安装可选推理依赖：在 01-app 内运行
`python deploy.py install --backend-only --inference`。这一步下载量较大；模型权重
由本数据包提供，不会自动下载。完整部署与限制说明见 01-app/README.md。

## 邮件分卷的拼接与校验

只有发送者使用 `--data-volumes-mb` 打包时，才会生成分卷。收齐所有
`02-data.zip.part001`、`02-data.zip.part002`……以及 `02-data.parts.json`，
将它们放到同一个文件夹。不能单独解压任一分卷，也不能漏掉索引文件。

如果分卷和 01-app 都放在“部署目录”，进入该目录运行：

```text
python 01-app/scripts/build_delivery.py --join-data . --output 02-data.zip
```

程序先验证全部分卷的大小与 SHA-256 校验值，通过后才生成普通 ZIP。
输出路径必须不存在；已有 02-data.zip 时改用新的文件名，不能覆盖原文件。
再用系统解压工具把 ZIP 解压到“部署目录”，得到同级的 02-data，合并后重启。
分卷、拼接后的 ZIP 和解压后的数据会同时占用磁盘，请预留空间。
视频本身已压缩，分卷只减小单个附件，不会显著减少总大小。
"""


@dataclass(frozen=True)
class Entry:
    path: str
    category: str
    bytes: int


def is_link(path: Path) -> bool:
    """Treat Windows junctions/reparse points like symlinks as well."""
    info = path.lstat()
    return path.is_symlink() or bool(
        getattr(info, "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    )


def safe_name(path: Path) -> bool:
    name = path.name.lower()
    return not (
        name.startswith(".env") or name.endswith((".pyc", ".pyo", ".bak", ".tmp"))
        or ".backup" in name or name in {".ds_store", "thumbs.db"}
    )


def walk_files(base: Path, skip_dirs=SKIP_DIRS):
    if not base.is_dir() or is_link(base):
        return
    for folder, dirs, files in os.walk(base, followlinks=False):
        directory = Path(folder)
        dirs[:] = sorted(
            name for name in dirs
            if name.lower() not in skip_dirs and safe_name(Path(name))
            and not is_link(directory / name)
        )
        for name in sorted(files):
            path = directory / name
            if safe_name(path) and not is_link(path) and path.is_file():
                yield path


def collect_files(root: Path, include_data: bool = True) -> list[Entry]:
    """Use an allowlist so local environments and raw training archives stay out."""
    root = root.resolve()
    found: dict[str, Entry] = {}

    def add(path: Path, category: str) -> None:
        if not path.is_file() or is_link(path) or not safe_name(path):
            return
        relative = path.relative_to(root)
        if any(is_link(root.joinpath(*relative.parts[:i])) for i in range(1, len(relative.parts))):
            return
        found[relative.as_posix()] = Entry(relative.as_posix(), category, path.stat().st_size)

    for path in root.iterdir():
        if path.name in ROOT_FILES or (path.name.startswith("requirements") and path.suffix == ".txt"):
            add(path, "app")
    for folder in ("scripts", "tests", "docs"):
        for path in walk_files(root / folder):
            if path.suffix.lower() in TEXT_SOURCE_SUFFIXES:
                add(path, "app")
    backend = root / BACKEND
    if backend.is_dir() and not is_link(backend):
        for child in backend.iterdir():
            if child.is_file():
                if child.suffix == ".py" or (child.name.startswith("requirements") and child.suffix == ".txt"):
                    add(child, "app")
            elif child.name.endswith("app") or child.name == "tests":
                for path in walk_files(child):
                    if path.suffix == ".py" or (path.name.startswith("requirements") and path.suffix == ".txt"):
                        add(path, "app")
    frontend = root / FRONTEND
    if frontend.is_dir() and not is_link(frontend):
        for path in frontend.iterdir():
            if path.name in UI_CONFIG_FILES or (
                path.is_file() and (path.name.startswith("tsconfig") or ".config." in path.name)
                and path.suffix.lower() in TEXT_SOURCE_SUFFIXES
            ):
                add(path, "app")
        for path in walk_files(frontend / "src"):
            if path.suffix.lower() in TEXT_SOURCE_SUFFIXES | UI_ASSET_SUFFIXES:
                add(path, "app")
        for path in walk_files(frontend / "public"):
            if path.relative_to(frontend / "public").parts[0] not in {"rose-pictures", "images"}:
                if path.suffix.lower() in UI_ASSET_SUFFIXES or path.name in {"robots.txt", "manifest.json"}:
                    add(path, "app")

    if include_data:
        for folder in RUNTIME_DIRS:
            for path in walk_files(backend / folder):
                add(path, "data")
        for folder in (
            "rose-tasks", "telecom-tasks", f"{FRONTEND}/public/rose-pictures",
            f"{FRONTEND}/public/images",
        ):
            for path in walk_files(root / folder):
                add(path, "data")
        for weight in ACTIVE_WEIGHTS:
            add(backend / weight, "data")
        dataset = backend / "wallapp" / "wall_damage_dataset"
        add(dataset / "metadata.json", "data")
        for path in walk_files(dataset / "labels"):
            if path.suffix == ".txt":
                add(path, "data")
        for model in ("tree_shrub_gnb_v1", "green_area_gnb_v1"):
            for path in walk_files(root / "models" / model):
                if path.suffix.lower() in {".npz", ".json", ".png", ".md"}:
                    add(path, "data")
        for path in walk_files(root / "measurement_data"):
            if path.suffix.lower() in DATA_ASSET_SUFFIXES or (
                path.suffix.lower() == ".ply" and path.relative_to(root / "measurement_data").parts[0] == "pointcloud_web"
            ):
                add(path, "data")
        for path in walk_files(root / "prelabel_output" / "instances_20260715"):
            if path.suffix.lower() in {".csv", ".json", ".png"}:
                add(path, "data")
        add(root / "prediction_output" / "prediction_data.json", "data")
    return sorted(found.values(), key=lambda entry: (entry.category, entry.path))


def new_output(path: Path, source_root: Path | None = None) -> Path:
    if ".." in path.parts:
        raise ValueError("Output paths must not contain '..'.")
    absolute = path.absolute()
    for candidate in (absolute, *absolute.parents):
        if candidate.exists() and is_link(candidate):
            raise ValueError(f"Output cannot use a symlink or junction: {candidate}")
    absolute = absolute.resolve()
    if absolute.exists():
        raise ValueError(f"Output already exists; choose a new path: {absolute}")
    if source_root is not None and absolute.is_relative_to(source_root.resolve()):
        relative = absolute.relative_to(source_root.resolve())
        if not relative.parts or relative.parts[0] != "delivery":
            raise ValueError("Inside the source project, output must be under delivery/.")
    return absolute


def write_json(path: Path, data: object) -> None:
    with path.open("x", encoding="utf-8") as output:
        json.dump(data, output, ensure_ascii=False, indent=2)
        output.write("\n")


def summary(entries: list[Entry]) -> dict:
    return {
        category: {
            "files": sum(entry.category == category for entry in entries),
            "bytes": sum(entry.bytes for entry in entries if entry.category == category),
        }
        for category in ("app", "data")
    }


class SplitZipWriter(io.RawIOBase):
    """A non-seekable ZIP destination, capped even when one video is very large."""

    def __init__(self, directory: Path, volume_bytes: int):
        super().__init__()
        if volume_bytes < 1:
            raise ValueError("Volume size must be positive.")
        self.directory = directory
        self.volume_bytes = volume_bytes
        self.parts: list[dict] = []
        self.current = None
        self.current_bytes = 0
        self.total_bytes = 0
        self.digest = hashlib.sha256()

    def writable(self):
        return True

    def tell(self):
        return self.total_bytes

    def _finish_part(self):
        if self.current is not None:
            self.current.close()
            self.parts.append({
                "name": Path(self.current.name).name, "bytes": self.current_bytes,
                "sha256": self.digest.hexdigest(),
            })
            self.current = None

    def write(self, data):
        view = memoryview(data)
        total = len(view)
        while view:
            if self.current is None:
                name = f"02-data.zip.part{len(self.parts) + 1:03d}"
                self.current = (self.directory / name).open("xb")
                self.current_bytes = 0
                self.digest = hashlib.sha256()
            size = min(len(view), self.volume_bytes - self.current_bytes)
            piece = view[:size]
            self.current.write(piece)
            self.digest.update(piece)
            self.current_bytes += size
            self.total_bytes += size
            view = view[size:]
            if self.current_bytes == self.volume_bytes:
                self._finish_part()
        return total

    def close(self):
        if not self.closed:
            self._finish_part()
        super().close()


def make_archive(folder: Path, destination) -> None:
    # Deflate is portable and compresses source well; precompressed media stays
    # essentially unchanged, so no video is re-encoded or degraded.
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        archive.writestr(f"{folder.name}/", b"")
        # This is already a filtered delivery folder. Retain intentionally
        # selected wall-dataset metadata and label files in the data archive.
        for path in walk_files(folder, skip_dirs=()):
            archive.write(path, f"{folder.name}/{path.relative_to(folder).as_posix()}")


def build_delivery(
    root: Path, output: Path, include_data: bool = True,
    volume_bytes: int | None = None, show_progress: bool = False,
) -> dict:
    root = root.resolve()
    output = new_output(output, root)
    entries = collect_files(root, include_data)
    if not any(entry.path == f"{FRONTEND}/package.json" for entry in entries):
        raise ValueError(f"Frontend package.json missing; not a project root: {root}")
    output.mkdir(parents=True, exist_ok=False)
    folders = {"app": output / "01-app", "data": output / "02-data"}
    for folder in folders.values():
        folder.mkdir()
    total_bytes = sum(entry.bytes for entry in entries)
    copied_bytes = 0
    next_progress = 1024 ** 3
    if show_progress:
        print(f"Copying {len(entries)} files ({total_bytes / 1024 ** 3:.2f} GiB)...", flush=True)
    for entry in entries:
        destination = folders[entry.category] / entry.path
        destination.parent.mkdir(parents=True, exist_ok=True)
        # Exclusive creation also protects against an unexpected concurrent write.
        with (root / entry.path).open("rb") as source, destination.open("xb") as target:
            for block in iter(lambda: source.read(1024 * 1024), b""):
                target.write(block)
                copied_bytes += len(block)
                if show_progress and copied_bytes >= next_progress:
                    print(
                        f"Copied {copied_bytes / 1024 ** 3:.1f}/{total_bytes / 1024 ** 3:.1f} GiB: {entry.path}",
                        flush=True,
                    )
                    next_progress += 1024 ** 3
        shutil.copystat(root / entry.path, destination)
    write_json(folders["app"] / "deployment-layout.json", {"data_directory": "../02-data"})
    with (folders["data"] / "README.md").open("x", encoding="utf-8") as instructions:
        instructions.write(DATA_README)
    if show_progress:
        print("Creating the small source ZIP...", flush=True)
    with (output / "01-app.zip").open("xb") as archive_file:
        make_archive(folders["app"], archive_file)
    if volume_bytes is not None and include_data:
        if show_progress:
            print("Creating capped data ZIP parts; large videos may take a while...", flush=True)
        with SplitZipWriter(output, volume_bytes) as writer:
            make_archive(folders["data"], writer)
        write_json(output / "02-data.parts.json", {"format": 1, "parts": writer.parts})
    result = {
        "format": 1, "created_at": datetime.now().astimezone().isoformat(),
        "data_included": include_data, "summary": summary(entries),
        "source_zip_bytes": (output / "01-app.zip").stat().st_size,
        "policy": "Runtime assets only; no environments, dependencies, old builds, raw training data, backups, or .env files.",
        "files": [entry.__dict__ for entry in entries],
        "generated_files": ["01-app/deployment-layout.json", "02-data/README.md"],
    }
    write_json(output / "manifest.json", result)
    return result


def join_data(directory: Path, destination: Path) -> Path:
    """Verify every part first, then reassemble a normal, portable ZIP file."""
    directory = directory.resolve()
    destination = new_output(destination)
    index = json.loads((directory / "02-data.parts.json").read_text(encoding="utf-8"))
    if index.get("format") != 1 or not isinstance(index.get("parts"), list) or not index["parts"]:
        raise ValueError("Invalid data-parts index.")
    paths = []
    for number, part in enumerate(index["parts"], 1):
        expected = f"02-data.zip.part{number:03d}"
        if not isinstance(part, dict) or part.get("name") != expected or PurePosixPath(part["name"]).name != expected:
            raise ValueError("Invalid or out-of-order data part name.")
        path = directory / expected
        if not path.is_file() or is_link(path) or path.stat().st_size != part.get("bytes"):
            raise ValueError(f"Missing or incomplete data part: {expected}")
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        if digest.hexdigest() != part.get("sha256"):
            raise ValueError(f"Data part checksum mismatch: {expected}")
        paths.append(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("xb") as output:
        for path in paths:
            with path.open("rb") as source:
                shutil.copyfileobj(source, output, length=1024 * 1024)
    return destination


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT, help="Source project root.")
    parser.add_argument("--output", type=Path, help="New delivery directory, or new ZIP path when joining.")
    parser.add_argument("--without-data", action="store_true", help="Create only the small app package; 02-data contains instructions but no assets.")
    parser.add_argument("--data-volumes-mb", type=int, help="Also create data ZIP parts, each at most this many MiB.")
    parser.add_argument("--dry-run", action="store_true", help="Print selected file counts and bytes without writing files.")
    parser.add_argument("--join-data", type=Path, metavar="PARTS_DIR", help="Join verified data parts into --output ZIP; does not extract files.")
    args = parser.parse_args(argv)
    try:
        if args.join_data is not None:
            if args.output is None or args.dry_run or args.without_data or args.data_volumes_mb is not None:
                parser.error("--join-data requires --output NEW_ZIP and cannot be combined with build options.")
            print(f"Restored ZIP: {join_data(args.join_data, args.output)}")
            return 0
        if args.data_volumes_mb is not None and (args.data_volumes_mb < 1 or args.without_data):
            parser.error("--data-volumes-mb must be positive and requires data to be included.")
        if args.dry_run:
            print(json.dumps(summary(collect_files(args.root, not args.without_data)), indent=2))
            return 0
        output = args.output or args.root / "delivery" / datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        volume_bytes = args.data_volumes_mb * 1024 * 1024 if args.data_volumes_mb else None
        result = build_delivery(args.root, output, not args.without_data, volume_bytes, show_progress=True)
        print(f"Delivery ready: {output.resolve()}")
        print(json.dumps({**result["summary"], "source_zip_bytes": result["source_zip_bytes"]}, indent=2))
        return 0
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        print(f"Delivery failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
