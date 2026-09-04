"""Run with: python -m unittest discover -s tests -p test_optional_deployment.py.

Uses a temporary, initially absent data directory and denies every torch/YOLO
import. No original video, model, database, or source directory is modified.
"""
from __future__ import annotations

import base64
import builtins
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest
import json
import runpy
import shutil
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class DeploymentPathResolutionTests(unittest.TestCase):
    def test_direct_import_honors_layout_and_environment(self):
        with tempfile.TemporaryDirectory(prefix="uav-layout-test-") as temporary:
            app_root = Path(temporary) / "renamed-app"
            backend = app_root / "uav-inspection-backend"
            backend.mkdir(parents=True)
            module_path = backend / "deployment_paths.py"
            shutil.copyfile(Path(__file__).resolve().parents[1] / "deployment_paths.py", module_path)
            with patch.dict(os.environ, {}, clear=True):
                legacy = runpy.run_path(str(module_path))
                self.assertEqual(legacy["DATA_ROOT"], app_root)
                (app_root / "deployment-layout.json").write_text(
                    json.dumps({"data_directory": "../02-data"}), encoding="utf-8")
                packaged = runpy.run_path(str(module_path))
                self.assertEqual(packaged["DATA_ROOT"], Path(temporary) / "02-data")
                self.assertFalse(packaged["DATA_ROOT"].exists())
                self.assertEqual(packaged["backend_path"]("heatmapdata", "videos"),
                                 Path(temporary) / "02-data" / "uav-inspection-backend" / "heatmapdata" / "videos")
                configured_root = Path(temporary) / "teacher-data"
                with patch.dict(os.environ, {"UAV_DATA_DIR": str(configured_root)}):
                    configured = runpy.run_path(str(module_path))
                    self.assertEqual(configured["DATA_ROOT"], configured_root)


class OptionalDeploymentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="uav-no-data-")
        cls.data_root = Path(cls.temp.name) / "02-data"
        cls.frontend_dist = Path(cls.temp.name) / "frontend-dist"
        cls.frontend_dist.mkdir()
        cls.frontend_html = '<!doctype html><html><body>Portable frontend fixture</body></html>'
        (cls.frontend_dist / "index.html").write_text(cls.frontend_html, encoding="utf-8")
        (cls.frontend_dist / "assets").mkdir()
        (cls.frontend_dist / "assets" / "app.js").write_text('console.log("fixture");', encoding="utf-8")
        (Path(cls.temp.name) / "private-deploy-note.txt").write_text("DO NOT EXPOSE", encoding="utf-8")
        cls.env_patch = patch.dict(os.environ, {
            "UAV_DATA_DIR": str(cls.data_root),
            "UAV_FRONTEND_DIST": str(cls.frontend_dist),
        })
        cls.env_patch.start()
        real_import = builtins.__import__
        real_find_spec = importlib.util.find_spec

        def deny_ai_import(name, *args, **kwargs):
            if name.split(".", 1)[0] in {"torch", "ultralytics"}:
                raise ModuleNotFoundError(f"Optional dependency deliberately absent: {name}")
            return real_import(name, *args, **kwargs)

        def absent_ai_spec(name, *args, **kwargs):
            if name.split(".", 1)[0] in {"torch", "ultralytics"}:
                return None
            return real_find_spec(name, *args, **kwargs)

        cls.import_patch = patch("builtins.__import__", side_effect=deny_ai_import)
        cls.spec_patch = patch("importlib.util.find_spec", side_effect=absent_ai_spec)
        cls.import_patch.start()
        cls.spec_patch.start()
        from fastapi.testclient import TestClient
        from heatmapapp.main import app
        cls.client = TestClient(app)
        cls.client.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.client.__exit__(None, None, None)
        cls.spec_patch.stop()
        cls.import_patch.stop()
        cls.env_patch.stop()
        cls.temp.cleanup()

    def test_01_start_and_empty_lists_without_data_or_ai(self):
        from deployment_paths import DATA_ROOT, backend_path
        self.assertEqual(DATA_ROOT, self.data_root)
        self.assertEqual(backend_path("heatmapdata", "videos"), self.data_root / "uav-inspection-backend" / "heatmapdata" / "videos")
        self.assertEqual(self.client.get("/api/health").json(), {"status": "ok"})
        self.assertEqual(self.client.get("/api/v1/tasks").json()["data"], [])
        self.assertEqual(self.client.get("/api/v1/rose/tasks/list").json()["tasks"], [])
        for endpoint in ("telecom", "power", "wall", "pruning"):
            with self.subTest(endpoint=endpoint):
                response = self.client.get(f"/api/v1/{endpoint}/videos")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["data"]["videos"], [])
        self.assertEqual(self.client.get("/api/v1/roof/tasks").status_code, 200)
        self.assertEqual(self.client.get("/api/v1/telecom/tasks").json()["data"]["tasks"], [])
        self.assertNotIn("torch", sys.modules)
        self.assertNotIn("ultralytics", sys.modules)

    def test_02_status_and_empty_measurements(self):
        status = self.client.get("/api/deployment/status").json()["data"]
        self.assertFalse(status["data_available"])
        self.assertFalse(status["inference_dependencies_installed"])
        self.assertFalse(status["inference_available"])
        overview = self.client.get("/api/v1/vegetation/overview")
        self.assertEqual(overview.status_code, 200)
        self.assertEqual(overview.json()["data"]["tasks"], [])
        self.assertIsNone(overview.json()["data"]["model"])
        prediction = self.client.get("/api/v1/predict/footfall")
        self.assertEqual(prediction.status_code, 200)
        self.assertEqual(prediction.json()["data"]["times"], [])

    def test_03_missing_database_is_not_an_error(self):
        response = self.client.get("/api/v1/pest/telemetry")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["mode"], "MOCK_DB_FAIL")

    def test_04_optional_inference_returns_actionable_503(self):
        import cv2
        import numpy as np
        ok, encoded = cv2.imencode(".jpg", np.zeros((64, 64, 3), dtype=np.uint8))
        self.assertTrue(ok)
        payload = {"image": base64.b64encode(encoded).decode("ascii")}
        for endpoint in ("rose", "telecom", "power", "pruning"):
            with self.subTest(endpoint=endpoint):
                health = self.client.get(f"/api/v1/{endpoint}/health")
                self.assertEqual(health.status_code, 200)
                health_data = health.json() if endpoint == "rose" else health.json()["data"]
                self.assertEqual(health_data["service_status"], "running")
                self.assertFalse(health_data["inference_available"])
                response = self.client.post(f"/api/v1/{endpoint}/detect", json=payload)
                self.assertEqual(response.status_code, 503, response.text)
                self.assertIn("02-data", response.json()["detail"])
        wall = self.client.post("/api/v1/wall/detect", json=payload)
        self.assertEqual(wall.status_code, 200, wall.text)
        heatmap = self.client.get("/api/v1/tasks/not-present/result")
        self.assertEqual(heatmap.status_code, 503)
        self.assertEqual(self.client.get("/api/video_feed/not-present").status_code, 503)
        with self.client.websocket_connect("/api/v1/ws/inference/not-present") as websocket:
            self.assertEqual(websocket.receive_json()["code"], 503)
            self.assertEqual(websocket.receive()["code"], 1013)
        from optional_inference import InferenceUnavailableError, load_yolo_model
        fake_model = self.data_root / "test-model.pt"
        fake_model.write_bytes(b"test")
        with self.assertRaisesRegex(InferenceUnavailableError, "requirements-inference.txt"):
            load_yolo_model(fake_model)

    def test_05_upload_and_playback_still_work_without_models(self):
        video_bytes = b"deployment-upload-fixture"
        response = self.client.post("/api/v1/tasks/upload", files={"video": ("sample.mp4", video_bytes, "video/mp4")})
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertFalse(payload["data"]["inferenceAvailable"])
        task_id = payload["data"]["taskId"]
        video_path = self.data_root / "uav-inspection-backend" / "heatmapdata" / "videos" / f"{task_id}.mp4"
        self.assertEqual(video_path.read_bytes(), video_bytes)
        self.assertEqual(self.client.get(f"/api/v1/media/{task_id}.mp4").content, video_bytes)
        state = self.client.get(f"/api/v1/tasks/{task_id}/status").json()["data"]
        self.assertEqual(state["status"], "FAILED")
        self.assertIn("02-data", state["error"])

    def test_06_realtime_channels_without_optional_files(self):
        with self.client.websocket_connect("/ws/v1/agent/chat") as websocket:
            self.assertEqual(websocket.receive_json()["role"], "agent")
        with self.client.websocket_connect("/ws/v1/system/logs") as websocket:
            self.assertEqual(websocket.receive_json()["level"], "INFO")
        with self.client.websocket_connect("/ws/v1/pest/telemetry") as websocket:
            self.assertIn("battery", websocket.receive_json())

    def test_07_frontend_routes_assets_and_path_boundary(self):
        for route in ("/", "/telecom", "/pest", "/heatmap-flow", "/power", "/roof", "/wall",
                      "/pruning", "/height", "/area", "/rose-digital", "/rose-yield", "/height/"):
            with self.subTest(route=route):
                response = self.client.get(route)
                self.assertEqual(response.status_code, 200)
                self.assertIn("text/html", response.headers["content-type"])
                self.assertEqual(response.text, self.frontend_html)
        asset = self.client.get("/assets/app.js")
        self.assertEqual(asset.status_code, 200)
        self.assertEqual(asset.text, 'console.log("fixture");')
        self.assertIn("javascript", asset.headers["content-type"])
        for path in ("/api/not-present", "/ws/not-present", "/assets/not-present.js",
                     "/rose-pictures/not-present.jpg", "/README.md", "/private-deploy-note.txt",
                     "/%2e%2e/private-deploy-note.txt", "/%2e%2e%5cprivate-deploy-note.txt"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 404, response.text)
                self.assertNotIn("DO NOT EXPOSE", response.text)
                self.assertNotIn(self.frontend_html, response.text)

    def test_08_optional_static_picture_uses_external_data_root(self):
        from deployment_paths import project_path
        picture = project_path("uav-inspection-ui", "public", "rose-pictures", "sample.jpg")
        picture.write_bytes(b"picture-fixture")
        response = self.client.get("/rose-pictures/sample.jpg")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"picture-fixture")


if __name__ == "__main__":
    unittest.main(verbosity=2)
