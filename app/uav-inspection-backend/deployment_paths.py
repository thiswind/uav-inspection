"""Resolve optional data independently of the source checkout and working directory."""
from __future__ import annotations

import os
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _resolve_data_root() -> Path:
    configured = os.environ.get("UAV_DATA_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    marker = PROJECT_ROOT / "deployment-layout.json"
    if marker.is_file():
        layout = json.loads(marker.read_text(encoding="utf-8"))
        return (PROJECT_ROOT / layout["data_directory"]).resolve()
    return PROJECT_ROOT


DATA_ROOT = _resolve_data_root()
BACKEND_DATA_ROOT = DATA_ROOT / "uav-inspection-backend"


def backend_path(*parts: str) -> Path:
    return BACKEND_DATA_ROOT.joinpath(*parts)


def project_path(*parts: str) -> Path:
    return DATA_ROOT.joinpath(*parts)
