"""第二阶段素材上传接口测试：python -m unittest discover -s tests -p test_uav_assets_upload.py.

使用临时数据目录，不触碰真实素材；覆盖白名单、路径穿越拒绝、防覆盖语义与前端深链接。
文件名以 u 开头保证排序在官方套件之后；断言一律从 deployment_paths 动态取路径，
因此单跑（本文件 pattern）与混跑（全量 discover）两种方式都成立。
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class AssetsUploadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="uav-assets-")
        cls.env_patch = patch.dict(os.environ, {"UAV_DATA_DIR": str(Path(cls.temp.name) / "02-data")})
        cls.env_patch.start()
        from fastapi.testclient import TestClient
        from heatmapapp.main import app
        cls.client = TestClient(app)
        cls.client.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.client.__exit__(None, None, None)
        cls.env_patch.stop()
        cls.temp.cleanup()

    def upload(self, category, name, content=b"x", **form):
        return self.client.post(
            "/api/v1/assets/upload",
            data={"category": category, **form},
            files={"files": (name, content, "application/octet-stream")},
        )

    def test_01_categories_listing(self):
        payload = self.client.get("/api/v1/assets/categories").json()
        self.assertEqual(payload["code"], 200)
        keys = {item["key"] for item in payload["data"]}
        self.assertIn("heatmap-videos", keys)
        self.assertIn("measurement-data", keys)
        self.assertIn("rose-pictures", keys)

    def test_02_upload_lands_in_category_directory(self):
        from deployment_paths import backend_path
        response = self.upload("heatmap-videos", "demo.mp4", b"\x00\x00\x00\x18ftyp")
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(len(data["saved"]), 1)
        self.assertEqual(data["skipped"], [])
        self.assertTrue((backend_path("heatmapdata", "videos") / "demo.mp4").is_file())

    def test_03_unknown_category_rejected(self):
        self.assertEqual(self.upload("etc-passwd", "x.txt").status_code, 422)

    def test_04_traversal_rejected(self):
        for bad_subdir in ("../..", "a/../../b", "..", "a/.."):
            with self.subTest(subdir=bad_subdir):
                response = self.upload("models", "x.txt", b"x", subdir=bad_subdir)
                self.assertEqual(response.status_code, 422)
        traversal_name = self.upload("models", "../../escape.txt")
        self.assertEqual(traversal_name.status_code, 200)
        payload = traversal_name.json()["data"]
        self.assertEqual([item["name"] for item in payload["saved"]], ["escape.txt"])
        landed = Path(payload["dir"]) / "escape.txt"
        self.assertTrue(landed.is_file())
        models_root = Path(str(payload["dir"]).split("/models")[0]) / "models"
        self.assertEqual(Path(payload["dir"]).resolve(), models_root.resolve())
        listing = self.client.get("/api/v1/assets/files", params={"category": "models"}).json()["data"]
        self.assertEqual([f["path"] for f in listing["files"]], ["escape.txt"])

    def test_05_duplicate_rejected_unless_overwrite(self):
        from deployment_paths import backend_path
        first = self.upload("wall-media", "dup.mp4", b"one")
        self.assertEqual(len(first.json()["data"]["saved"]), 1)
        second = self.upload("wall-media", "dup.mp4", b"two")
        self.assertEqual(second.json()["data"]["skipped"][0]["name"], "dup.mp4")
        target = backend_path("walldata", "media") / "dup.mp4"
        self.assertEqual(target.read_bytes(), b"one")
        third = self.upload("wall-media", "dup.mp4", b"three", overwrite="true")
        self.assertEqual(target.read_bytes(), b"three")

    def test_06_subdir_upload_and_listing(self):
        response = self.upload("measurement-data", "green_area_summary.json", b"{}",
                               subdir="task-2026/demo")
        self.assertEqual(response.status_code, 200)
        listing = self.client.get("/api/v1/assets/files",
                                  params={"category": "measurement-data",
                                          "subdir": "task-2026/demo"}).json()["data"]
        self.assertEqual(listing["count"], 1)
        self.assertEqual(listing["files"][0]["path"], "task-2026/demo/green_area_summary.json")

    def test_07_assets_page_deep_link_serves_index(self):
        page = self.client.get("/assets")
        self.assertEqual(page.status_code, 200)


if __name__ == "__main__":
    unittest.main()
