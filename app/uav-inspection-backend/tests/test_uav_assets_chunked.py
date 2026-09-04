"""分片上传接口测试：python -m unittest discover -s tests -p test_uav_assets_chunked.py.

使用临时数据目录，不触碰真实素材；覆盖 init/chunk/status/complete 全流程、
断点续传（缺片 409 → status 补片 → 合并）、秒传与并发重名去重、
分片参数校验与总量校验、7 天废弃分片清理。
与官方套件混跑时 CHUNk_SIZE 可能已被其他套件冻结，故目标文件大小一律
从 assetsapp.api.CHUNK_SIZE 动态推导（恒为 2.5 片 = 3 片），单跑/混跑都成立。
"""
from __future__ import annotations

import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _blob(total: int) -> bytes:
    pattern = bytes(range(256)) * 64
    out = bytearray()
    while len(out) < total:
        out += pattern
    return bytes(out[:total])


class AssetsChunkedUploadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="uav-chunk-")
        cls.env_patch = patch.dict(os.environ, {
            "UAV_DATA_DIR": str(Path(cls.temp.name) / "02-data"),
            "UAV_CHUNK_SIZE": "64",
        })
        cls.env_patch.start()
        from fastapi.testclient import TestClient
        from heatmapapp.main import app
        from assetsapp import api as assets_api
        cls.assets_api = assets_api
        cls.chunk_size = assets_api.CHUNK_SIZE
        cls.total_size = cls.chunk_size * 2 + cls.chunk_size // 2  # 2.5 片 → 3 片
        cls.client = TestClient(app)
        cls.client.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.client.__exit__(None, None, None)
        cls.env_patch.stop()
        cls.temp.cleanup()

    def init(self, name, size, **form):
        return self.client.post("/api/v1/assets/upload/init", data={
            "category": "models", "filename": name, "size": str(size), **form,
        })

    def chunk(self, upload_id, index, blob):
        return self.client.post("/api/v1/assets/upload/chunk", data={
            "upload_id": upload_id, "index": str(index),
        }, files={"file": (f"part-{index}", blob, "application/octet-stream")})

    def complete(self, upload_id):
        return self.client.post("/api/v1/assets/upload/complete", data={"upload_id": upload_id})

    def status(self, upload_id):
        return self.client.get("/api/v1/assets/upload/status", params={"upload_id": upload_id})

    def workdir(self, upload_id):
        from deployment_paths import DATA_ROOT
        return Path(DATA_ROOT) / ".upload-tmp" / upload_id

    def test_01_full_chunked_flow_merges_exact_bytes(self):
        content = _blob(self.total_size)
        response = self.init("chunked-full.bin", self.total_size)
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["mode"], "chunked")
        upload_id = data["uploadId"]
        self.assertEqual(data["totalChunks"], 3)
        self.assertEqual(data["received"], [])

        for index in range(3):
            piece = content[index * self.chunk_size:(index + 1) * self.chunk_size]
            sent = self.chunk(upload_id, index, piece)
            self.assertEqual(sent.status_code, 200)
            self.assertEqual(sent.json()["data"]["received"],
                             list(range(index + 1)))

        done = self.complete(upload_id)
        self.assertEqual(done.status_code, 200)
        self.assertEqual(done.json()["data"]["chunks"], 3)

        from deployment_paths import project_path
        target = project_path("models") / "chunked-full.bin"
        self.assertTrue(target.is_file())
        self.assertEqual(target.read_bytes(), content)
        self.assertFalse(self.workdir(upload_id).exists())

    def test_02_resume_after_interrupt(self):
        content = _blob(self.total_size)
        upload_id = self.init("chunked-resume.bin", self.total_size).json()["data"]["uploadId"]
        self.chunk(upload_id, 0, content[:self.chunk_size])
        self.chunk(upload_id, 2, content[2 * self.chunk_size:])

        early = self.complete(upload_id)
        self.assertEqual(early.status_code, 409)
        self.assertIn("分片不全", early.json()["detail"])

        state = self.status(upload_id)
        self.assertEqual(state.status_code, 200)
        self.assertEqual(state.json()["data"]["received"], [0, 2])
        self.assertEqual(state.json()["data"]["totalChunks"], 3)
        self.assertEqual(state.json()["data"]["filename"], "chunked-resume.bin")

        # 补传缺口分片后合并，字节序必须与原文件一致
        missing = content[self.chunk_size:2 * self.chunk_size]
        self.assertEqual(self.chunk(upload_id, 1, missing).status_code, 200)
        done = self.complete(upload_id)
        self.assertEqual(done.status_code, 200)

        from deployment_paths import project_path
        target = project_path("models") / "chunked-resume.bin"
        self.assertEqual(target.read_bytes(), content)

    def test_03_instant_hit_and_dedupe_on_complete(self):
        from deployment_paths import project_path
        content = _blob(self.total_size)
        target = project_path("models") / "chunked-instant.bin"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)

        hit = self.init("chunked-instant.bin", self.total_size)
        self.assertEqual(hit.status_code, 200)
        self.assertEqual(hit.json()["data"]["mode"], "instant")
        self.assertEqual(hit.json()["data"]["size"], self.total_size)

        forced = self.init("chunked-instant.bin", self.total_size, overwrite="true")
        self.assertEqual(forced.json()["data"]["mode"], "chunked")
        upload_id = forced.json()["data"]["uploadId"]
        for index in range(3):
            self.chunk(upload_id, index,
                       content[index * self.chunk_size:(index + 1) * self.chunk_size])
        done = self.complete(upload_id)
        self.assertEqual(done.status_code, 200)
        self.assertEqual(target.read_bytes(), content)

        # 竞态去重：先 init（此时目标已存在 → 会秒传命中拿不到 uploadId），
        # 故先删目标文件 init，再在分片期间把文件写回，complete 未开启覆盖 → 保留既有并清理分片
        target.unlink()
        race_id = self.init("chunked-instant.bin", self.total_size).json()["data"]["uploadId"]
        target.write_bytes(content)
        for index in range(3):
            self.chunk(race_id, index,
                       content[index * self.chunk_size:(index + 1) * self.chunk_size])
        dedup = self.complete(race_id)
        self.assertEqual(dedup.status_code, 200)
        self.assertIn("deduplicated", dedup.json()["data"])
        self.assertEqual(target.read_bytes(), content)
        self.assertFalse(self.workdir(race_id).exists())

    def test_04_param_and_size_validation(self):
        bad_id = self.chunk("not-a-hex-id", 0, b"x")
        self.assertEqual(bad_id.status_code, 422)

        ghost = self.status("0" * 32)
        self.assertEqual(ghost.status_code, 404)

        upload_id = self.init("chunked-guard.bin", self.total_size).json()["data"]["uploadId"]
        self.assertEqual(self.chunk(upload_id, -1, b"x").status_code, 422)
        self.assertEqual(self.chunk(upload_id, 99, b"x").status_code, 422)  # 分片号越界直接拒收

        content = _blob(self.total_size)
        self.chunk(upload_id, 0, content[:self.chunk_size])
        self.chunk(upload_id, 1, content[self.chunk_size:2 * self.chunk_size])
        self.chunk(upload_id, 2, b"short")  # 尾片短传 → 总量不符
        mismatch = self.complete(upload_id)
        self.assertEqual(mismatch.status_code, 409)
        self.assertIn("总大小", mismatch.json()["detail"])

        self.chunk(upload_id, 2, content[2 * self.chunk_size:])
        done = self.complete(upload_id)
        self.assertEqual(done.status_code, 200)

        from deployment_paths import project_path
        target = project_path("models") / "chunked-guard.bin"
        self.assertEqual(target.read_bytes(), content)

    def test_05_init_rejects_bad_input(self):
        self.assertEqual(self.init("x.bin", 0).status_code, 422)
        self.assertEqual(self.init("x.bin", -5).status_code, 422)
        self.assertEqual(self.init("../escape.bin", 10).status_code, 200)  # 名字清洗落盘为 escape.bin
        data = self.init("x.bin", 10, category="etc-passwd")
        self.assertEqual(data.status_code, 422)

    def test_06_stale_tmp_cleaned_after_seven_days(self):
        from deployment_paths import DATA_ROOT
        stale_root = Path(DATA_ROOT) / ".upload-tmp"
        stale_dir = stale_root / ("f" * 32)
        stale_dir.mkdir(parents=True, exist_ok=True)
        (stale_dir / "0.part").write_bytes(b"junk")
        old = time.time() - 8 * 86400
        os.utime(stale_dir, (old, old))

        fresh_id = self.init("chunked-fresh.bin", 10).json()["data"]["uploadId"]
        self.assertFalse(stale_dir.exists())
        self.assertTrue(self.workdir(fresh_id).is_dir())
        self.complete(fresh_id)


if __name__ == "__main__":
    unittest.main()
