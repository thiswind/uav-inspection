import json
from pathlib import Path

from fastapi import APIRouter
from deployment_paths import backend_path, project_path

router = APIRouter()

PREDICT_DATA_CANDIDATES = [
    project_path("prediction_output", "prediction_data.json"),
    backend_path("prediction_output", "prediction_data.json"),
    backend_path("heatmapdata", "prediction_data.json"),
]


def _load_predict_data():
    for path in PREDICT_DATA_CANDIDATES:
        if path.exists():
            with path.open("r", encoding="utf-8") as f:
                return json.load(f)
    return None


@router.get("/footfall")
async def get_footfall_prediction():
    data = _load_predict_data()

    if data is None:
        return {
            "code": 200,
            "data": {
                "times": [],
                "actual": [],
                "predicted": [],
                "peaks": [],
                "gaussParams": {},
            },
            "message": "Prediction data has not been generated yet.",
        }

    return {
        "code": 200,
        "data": data,
        "message": "success",
    }
