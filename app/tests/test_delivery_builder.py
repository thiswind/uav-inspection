"""Delivery packaging tests; run with python -m unittest discover -s tests."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import sys
import unittest
import zipfile


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "build_delivery.py"
SPEC = importlib.util.spec_from_file_location("build_delivery", SCRIPT)
delivery = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = delivery
SPEC.loader.exec_module(delivery)


class DeliveryBuilderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "project"
        self.root.mkdir()

    def put(self, relative, content=b"fixture"):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def fixtures(self):
        app_files = [
            "README.md", "deploy.py", "setup.bat", "start.sh",
            "scripts/build_delivery.py", "scripts/requirements-green-area.txt",
            "docs/deployment.md", "tests/test_example.py",
            "uav-inspection-backend/deployment_paths.py",
            "uav-inspection-backend/requirements.txt",
            "uav-inspection-backend/requirements-base-lock.txt",
            "uav-inspection-backend/tests/test_optional_deployment.py",
            "uav-inspection-backend/heatmapapp/main.py",
            "uav-inspection-backend/treeapp/tools/train_pruning_model.py",
            "uav-inspection-ui/package.json", "uav-inspection-ui/package-lock.json",
            "uav-inspection-ui/index.html", "uav-inspection-ui/vite.config.ts",
            "uav-inspection-ui/tsconfig.app.json", "uav-inspection-ui/src/App.vue",
            "uav-inspection-ui/src/assets/icon.svg", "uav-inspection-ui/public/favicon.svg",
        ]
        data_files = [
            "uav-inspection-backend/heatmapdata/videos/video.mp4",
            "uav-inspection-backend/heatmapdata/videos/video.srt",
            "uav-inspection-backend/heatmapdata/snapshots/frame.jpg",
            "uav-inspection-backend/pestdata/mock_track.json",
            "uav-inspection-backend/walldata/media/wall.mp4",
            "uav-inspection-backend/walldata/logs/logs.json",
            "uav-inspection-backend/wallapp/wall_damage_dataset/metadata.json",
            "uav-inspection-backend/wallapp/wall_damage_dataset/labels/train/label.txt",
            "uav-inspection-backend/heatmapweight/renliu.pt",
            "uav-inspection-backend/roseapp/rose-detect-best.pt",
            "uav-inspection-backend/wallapp/wall-damage-best.pt",
            "uav-inspection-backend/rose-tasks/task.json", "rose-tasks/task.json",
            "models/tree_shrub_gnb_v1/model.npz", "models/green_area_gnb_v1/metrics.json",
            "measurement_data/task_a/green_area_overview.jpg",
            "measurement_data/pointcloud_web/task_a/scene.ply",
            "prelabel_output/instances_20260715/task_a/tree_instances.csv",
            "prediction_output/prediction_data.json",
            "uav-inspection-ui/public/rose-pictures/plot.JPG",
            "uav-inspection-ui/public/images/tiles/tile.png",
            "uav-inspection-ui/public/images/satellite-base.png",
        ]
        excluded_files = [
            "package.json", "package-lock.json", "yolo11n.pt",
            ".env", ".venv/Lib/code.py", "node_modules/test.js",
            "uav-inspection-backend/venv/Lib/code.py",
            "uav-inspection-backend/yolo11n.pt",
            "uav-inspection-backend/heatmapdata/debug_contact_sheets/frame.jpg",
            "uav-inspection-backend/roseapp/.env.production",
            "uav-inspection-backend/roseapp/runs/train/code.py",
            "uav-inspection-backend/wallapp/wall-damage-best.backup.pt",
            "uav-inspection-backend/wallapp/wall_damage_dataset/images/train/image.jpg",
            "uav-inspection-backend/wallapp/wall_damage_dataset/data.yaml",
            "uav-inspection-backend/powerapp/__pycache__/cached.pyc",
            "uav-inspection-backend/tests/__pycache__/test_optional_deployment.pyc",
            "uav-inspection-backend/tests/.env",
            "uav-inspection-backend/pestdata/.env",
            "uav-inspection-ui/.env.production", "uav-inspection-ui/dist/index.html",
            "uav-inspection-ui/node_modules/pkg/code.ts",
            "uav-inspection-ui/public/demo.mp4", "uav-inspection-ui/src/cache.pyc",
            "scripts/__pycache__/code.pyc", "training_data/archive.json",
            "webodm_downloads/huge.laz", "measurement_data/task_a/raw.laz",
            "measurement_data/task_a/full.ply",
            "prelabel_output/instances_20260715/task_a/tree_instances_colored.ply",
            "prelabel_output/semantic_20260715/data.json",
            "models/old_model/model.npz", "prediction_output/screenshot.png",
        ]
        for path in app_files + data_files + excluded_files:
            self.put(path)
        return app_files, data_files, excluded_files

    def test_allowlist_separates_sources_and_optional_runtime_assets(self):
        app_files, data_files, excluded = self.fixtures()
        entries = delivery.collect_files(self.root)
        self.assertEqual({entry.path for entry in entries if entry.category == "app"}, set(app_files))
        self.assertEqual({entry.path for entry in entries if entry.category == "data"}, set(data_files))
        self.assertFalse({entry.path for entry in entries} & set(excluded))

    def test_source_only_zip_has_marker_and_no_data_or_environments(self):
        app_files, _, _ = self.fixtures()
        output = self.base / "email"
        original = self.root / "uav-inspection-backend/heatmapdata/videos/video.mp4"
        before = original.read_bytes()
        result = delivery.build_delivery(self.root, output, include_data=False)
        self.assertEqual(result["summary"]["data"], {"files": 0, "bytes": 0})
        self.assertTrue((output / "02-data").is_dir())
        self.assertEqual({path.name for path in (output / "02-data").iterdir()}, {"README.md"})
        instructions = (output / "02-data" / "README.md").read_text(encoding="utf-8")
        self.assertIn("--join-data . --output 02-data.zip", instructions)
        self.assertIn("02-data.parts.json", instructions)
        self.assertIn("首次安装程序需要联网", instructions)
        self.assertIn("当前界面未使用这些文件", instructions)
        self.assertEqual(result["generated_files"], ["01-app/deployment-layout.json", "02-data/README.md"])
        self.assertEqual(original.read_bytes(), before)
        with zipfile.ZipFile(output / "01-app.zip") as archive:
            expected = {f"01-app/{name}" for name in app_files}
            expected.update({"01-app/", "01-app/deployment-layout.json"})
            self.assertEqual(set(archive.namelist()), expected)
            self.assertFalse(any("/public/images/" in name for name in archive.namelist()))
            marker = json.loads(archive.read("01-app/deployment-layout.json"))
            self.assertEqual(marker, {"data_directory": "../02-data"})

    def test_data_is_copied_with_original_relative_paths(self):
        _, data_files, _ = self.fixtures()
        output = self.base / "email"
        delivery.build_delivery(self.root, output)
        actual = {path.relative_to(output / "02-data").as_posix() for path in (output / "02-data").rglob("*") if path.is_file()}
        self.assertEqual(actual, set(data_files) | {"README.md"})
        self.assertFalse((output / "02-data.zip").exists())

    def test_existing_output_is_never_overwritten(self):
        self.fixtures()
        output = self.base / "existing"
        output.mkdir()
        sentinel = output / "keep.txt"
        sentinel.write_text("keep", encoding="utf-8")
        with self.assertRaises(ValueError):
            delivery.build_delivery(self.root, output)
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep")

    def test_traversal_and_output_among_source_files_are_rejected(self):
        for path in (self.base / "nested" / ".." / "escape", self.root / "scripts" / "output"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                delivery.new_output(path, self.root)

    def test_symlinks_are_excluded(self):
        self.fixtures()
        external = self.base / "outside.py"
        external.write_text("private", encoding="utf-8")
        link = self.root / "scripts" / "linked.py"
        try:
            link.symlink_to(external)
        except (OSError, NotImplementedError):
            self.skipTest("Symlink creation unavailable on this host")
        self.assertNotIn("scripts/linked.py", {entry.path for entry in delivery.collect_files(self.root)})

    def test_split_zip_caps_every_part_and_round_trips_large_single_file(self):
        self.put("uav-inspection-ui/package.json", b"{}")
        # Pseudorandom-looking bytes avoid a tiny compressed test fixture.
        import random
        content = random.Random(72).randbytes(5000)
        self.put("uav-inspection-backend/heatmapdata/videos/big.mp4", content)
        output = self.base / "delivery"
        delivery.build_delivery(self.root, output, volume_bytes=512)
        parts = sorted(output.glob("02-data.zip.part*"))
        self.assertGreater(len(parts), 1)
        self.assertTrue(all(0 < part.stat().st_size <= 512 for part in parts))
        destination = self.base / "restored.zip"
        delivery.join_data(output, destination)
        with zipfile.ZipFile(destination) as archive:
            self.assertEqual(archive.read("02-data/uav-inspection-backend/heatmapdata/videos/big.mp4"), content)
            self.assertIsNone(archive.testzip())
        with self.assertRaises(ValueError):
            delivery.join_data(output, destination)

    def test_data_archive_retains_intentionally_selected_dataset_labels(self):
        _, data_files, _ = self.fixtures()
        output = self.base / "delivery"
        delivery.build_delivery(self.root, output, volume_bytes=512)
        destination = self.base / "restored.zip"
        delivery.join_data(output, destination)
        with zipfile.ZipFile(destination) as archive:
            self.assertEqual(set(archive.namelist()), {"02-data/", "02-data/README.md"} | {f"02-data/{path}" for path in data_files})

    def test_tampered_part_does_not_create_destination(self):
        self.put("uav-inspection-ui/package.json", b"{}")
        self.put("uav-inspection-backend/heatmapdata/videos/video.mp4", b"video")
        output = self.base / "delivery"
        delivery.build_delivery(self.root, output, volume_bytes=128)
        part = next(output.glob("02-data.zip.part*"))
        part.write_bytes(b"x" * part.stat().st_size)
        destination = self.base / "restored.zip"
        with self.assertRaises(ValueError):
            delivery.join_data(output, destination)
        self.assertFalse(destination.exists())

    def test_part_index_path_traversal_is_rejected(self):
        output = self.base / "parts"
        output.mkdir()
        (output / "02-data.parts.json").write_text(json.dumps({
            "format": 1, "parts": [{"name": "../private", "bytes": 1, "sha256": "unused"}],
        }), encoding="utf-8")
        destination = self.base / "restored.zip"
        with self.assertRaises(ValueError):
            delivery.join_data(output, destination)
        self.assertFalse(destination.exists())


if __name__ == "__main__":
    unittest.main()
