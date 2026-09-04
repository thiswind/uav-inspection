from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from statistics import median

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from deployment_paths import project_path
from uav_url_prefix import prefixed


router = APIRouter()

HEIGHT_MODEL_DIR = project_path('models', 'tree_shrub_gnb_v1')
AREA_MODEL_DIR = project_path('models', 'green_area_gnb_v1')
INSTANCE_ROOT = project_path('prelabel_output', 'instances_20260715')
MEASUREMENT_ROOT = project_path('measurement_data')
WEB_POINTCLOUD_ROOT = MEASUREMENT_ROOT / 'pointcloud_web'

TASKS = [
    {'key': 'task_01_xinxixueyuan_1', 'name': '信息学院1号地', 'uuid': '5795b0c1-9064-4a0b-97ea-82369405cdb9', 'images': 120},
    {'key': 'task_02_xinxixueyuan_2', 'name': '信息学院2号地', 'uuid': '750daf18-9e61-49e7-81b1-4a04889c8b08', 'images': 356},
    {'key': 'task_03_meiguiyuan_2', 'name': '玫瑰园2号地', 'uuid': '1def4f71-2b41-4e79-8aa0-c0497ee5368e', 'images': 474},
    {'key': 'task_04_meiguiyuan_1', 'name': '玫瑰园1号地', 'uuid': 'f1423e09-b0cc-4102-ab3d-e51ffeeadc8e', 'images': 129},
    {'key': 'task_05_meiguiyuan_3', 'name': '玫瑰园3号地', 'uuid': '3fe9e04f-b858-4615-ac0e-cf20987f4e3b', 'images': 90},
]
TASK_INDEX = {task['key']: task for task in TASKS}


def _read_json(path: Path) -> dict:
    if not path.exists():
        raise HTTPException(status_code=503, detail=f'未安装可选测量数据 {path.name}；请放入 02-data 数据包或设置 UAV_DATA_DIR。')
    return json.loads(path.read_text(encoding='utf-8'))


def _tree_rows(task_key: str) -> list[dict[str, float | int]]:
    path = INSTANCE_ROOT / task_key / 'tree_instances.csv'
    if not path.exists():
        return []
    rows: list[dict[str, float | int]] = []
    with path.open('r', encoding='utf-8-sig', newline='') as stream:
        for row in csv.DictReader(stream):
            x_span = float(row['x_max']) - float(row['x_min'])
            y_span = float(row['y_max']) - float(row['y_min'])
            rows.append({
                'tree_id': int(row['tree_id']),
                'points': int(row['points']),
                'height_m': round(float(row['height_p99']), 2),
                'crown_width_m': round(max(x_span, y_span), 2),
                'crown_area_m2': round(math.pi * x_span * y_span / 4, 2),
                'centroid_x': round(float(row['centroid_x']), 3),
                'centroid_y': round(float(row['centroid_y']), 3),
                'x_min': float(row['x_min']),
                'x_max': float(row['x_max']),
                'y_min': float(row['y_min']),
                'y_max': float(row['y_max']),
                'z_min': float(row['z_min']),
                'z_max': float(row['z_max']),
            })
    return rows


def _task_summary(task: dict) -> dict:
    key = task['key']
    instance = _read_json(INSTANCE_ROOT / key / 'summary.json')
    shrub = _read_json(MEASUREMENT_ROOT / key / 'shrub_summary.json')
    green = _read_json(MEASUREMENT_ROOT / key / 'green_area_summary.json')
    trees = _tree_rows(key)
    heights = [float(tree['height_m']) for tree in trees]
    return {
        **task,
        'status': 'completed',
        'epsg': 32648,
        'tree_count': len(trees),
        'tree_points': instance.get('assigned_points', 0),
        'unassigned_tree_points': instance.get('unassigned_points', 0),
        'average_height_m': round(sum(heights) / len(heights), 2) if heights else 0,
        'median_height_m': round(median(heights), 2) if heights else 0,
        'max_height_m': round(max(heights), 2) if heights else 0,
        'shrub_area_m2': shrub.get('area_m2', 0),
        'shrub_patch_count': shrub.get('patch_count', 0),
        'largest_shrub_patch_m2': shrub.get('largest_patch_m2', 0),
        'shrub_mean_height_m': shrub.get('mean_height_m', 0),
        'green_area_m2': green.get('area_m2', 0),
        'green_patch_count': green.get('patch_count', 0),
        'largest_green_patch_m2': green.get('largest_patch_m2', 0),
        'green_coverage_ratio': green.get('coverage_ratio', 0),
        'green_mean_confidence': green.get('mean_confidence', 0),
        'tree_preview_url': prefixed(f'/api/v1/vegetation/tasks/{key}/assets/tree-overview'),
        'shrub_preview_url': prefixed(f'/api/v1/vegetation/tasks/{key}/assets/shrub-overview'),
        'green_preview_url': prefixed(f'/api/v1/vegetation/tasks/{key}/assets/green-overview'),
        'webodm_url': 'http://localhost:8000/dashboard/?project_task_open=1',
    }


def _height_model_payload() -> dict:
    metrics = _read_json(HEIGHT_MODEL_DIR / 'metrics.json')
    validation = metrics['validation_metrics']
    return {
        'name': '乔木/灌木轻量分类模型 V1',
        'algorithm': metrics['model'],
        'description': 'RGB 派生特征 + 局部离地高度',
        'accuracy': validation['accuracy'],
        'macro_f1': validation['macro_f1'],
        'classes': validation['classes'],
        'confusion_matrix': validation['confusion_matrix'],
        'training_samples': sum(item['sampled'] for item in metrics['sample_counts']['train'].values()),
        'validation_samples': sum(item['sampled'] for item in metrics['sample_counts']['val'].values()),
        'status': 'baseline',
        'badge': '基线模型',
        'validation_title': '实例留出验证',
        'validation_note': '树 ID 8-10 与灌木 ID 2 未参与训练。',
        'data_note': '当前仅 10 棵人工树实例和 2 片灌木真值。',
        'confusion_url': prefixed('/api/v1/vegetation/models/height/confusion'),
    }


def _area_model_payload() -> dict:
    metrics = _read_json(AREA_MODEL_DIR / 'metrics.json')
    validation = metrics['validation_metrics']
    return {
        'name': '绿化面积像素分类模型 V1',
        'algorithm': metrics['model'],
        'description': 'RGB 颜色派生特征 + GeoTIFF 像元面积',
        'accuracy': validation['accuracy'],
        'macro_f1': validation['macro_f1'],
        'classes': validation['classes'],
        'confusion_matrix': validation['confusion_matrix'],
        'training_samples': metrics['training_samples'],
        'validation_samples': metrics['validation_samples'],
        'status': 'trained',
        'badge': '已训练',
        'validation_title': '五折任务级留出验证',
        'validation_note': '每个 WebODM 任务各作为一次完整验证集。',
        'data_note': '5 个任务自行生成高置信伪标签；现场交付仍需抽样复核。',
        'confusion_url': prefixed('/api/v1/vegetation/models/area/confusion'),
    }


@router.get('/overview')
async def vegetation_overview() -> dict[str, object]:
    height_model = _height_model_payload() if (HEIGHT_MODEL_DIR / 'metrics.json').is_file() else None
    area_model = _area_model_payload() if (AREA_MODEL_DIR / 'metrics.json').is_file() else None
    tasks = [
        _task_summary(task) for task in TASKS
        if all(path.is_file() for path in (
            INSTANCE_ROOT / task['key'] / 'summary.json',
            MEASUREMENT_ROOT / task['key'] / 'shrub_summary.json',
            MEASUREMENT_ROOT / task['key'] / 'green_area_summary.json',
        ))
    ]
    return {
        'code': 200,
        'message': 'success' if tasks else '尚未安装可选测量数据；可继续使用其他功能，之后放入 02-data 数据包。',
        'data': {
            'model': height_model,
            'models': {'height': height_model, 'area': area_model},
            'tasks': tasks,
            'totals': {
                'tasks': len(tasks),
                'trees': sum(task['tree_count'] for task in tasks),
                'shrub_area_m2': round(sum(task['shrub_area_m2'] for task in tasks), 2),
                'green_area_m2': round(sum(task['green_area_m2'] for task in tasks), 2),
                'images': sum(task['images'] for task in tasks),
            },
        },
    }


@router.get('/tasks/{task_key}/trees')
async def vegetation_trees(
    task_key: str,
    query: str = Query('', max_length=32),
    minimum_height: float = Query(0, ge=0, le=100),
    sort_by: str = Query('height_m', pattern='^(tree_id|height_m|crown_width_m|points)$'),
    descending: bool = True,
) -> dict[str, object]:
    if task_key not in TASK_INDEX:
        raise HTTPException(status_code=404, detail='任务不存在')
    rows = [row for row in _tree_rows(task_key) if float(row['height_m']) >= minimum_height]
    if query.strip():
        token = query.strip().upper().removeprefix('T-')
        rows = [row for row in rows if token in str(row['tree_id'])]
    rows.sort(key=lambda row: row[sort_by], reverse=descending)
    return {'code': 200, 'message': 'success', 'data': {'items': rows, 'total': len(rows)}}


@router.get('/tasks/{task_key}/scene')
async def vegetation_scene(task_key: str) -> dict[str, object]:
    if task_key not in TASK_INDEX:
        raise HTTPException(status_code=404, detail='任务不存在')
    metadata = _read_json(WEB_POINTCLOUD_ROOT / task_key / 'scene.json')
    green_model = _read_json(AREA_MODEL_DIR / 'model.json')
    return {
        'code': 200,
        'message': 'success',
        'data': {
            **metadata,
            'point_cloud_url': prefixed(f'/api/v1/vegetation/tasks/{task_key}/assets/scene-ply'),
            'green_model': green_model,
        },
    }


@router.get('/tasks/{task_key}/assets/{asset_name}')
async def vegetation_asset(task_key: str, asset_name: str) -> FileResponse:
    if task_key not in TASK_INDEX:
        raise HTTPException(status_code=404, detail='任务不存在')
    assets = {
        'tree-overview': INSTANCE_ROOT / task_key / 'tree_instances_overview.png',
        'shrub-overview': MEASUREMENT_ROOT / task_key / 'shrub_overview.png',
        'green-overview': MEASUREMENT_ROOT / task_key / 'green_area_overview.jpg',
        'green-mask': MEASUREMENT_ROOT / task_key / 'green_area_mask.png',
        'trees-csv': INSTANCE_ROOT / task_key / 'tree_instances.csv',
        'scene-ply': WEB_POINTCLOUD_ROOT / task_key / 'scene.ply',
    }
    path = assets.get(asset_name)
    if path is None or not path.exists():
        raise HTTPException(status_code=404, detail='资源不存在')
    media_type = {
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.csv': 'text/csv',
        '.ply': 'application/octet-stream',
    }.get(path.suffix, 'application/octet-stream')
    return FileResponse(path, media_type=media_type, filename=path.name if path.suffix == '.csv' else None)


@router.get('/model/confusion')
async def vegetation_confusion() -> FileResponse:
    path = HEIGHT_MODEL_DIR / 'confusion_matrix.png'
    if not path.exists():
        raise HTTPException(status_code=404, detail='混淆矩阵不存在')
    return FileResponse(path, media_type='image/png')


@router.get('/models/{model_key}/confusion')
async def vegetation_model_confusion(model_key: str) -> FileResponse:
    model_dirs = {'height': HEIGHT_MODEL_DIR, 'area': AREA_MODEL_DIR}
    model_dir = model_dirs.get(model_key)
    if model_dir is None:
        raise HTTPException(status_code=404, detail='模型不存在')
    path = model_dir / 'confusion_matrix.png'
    if not path.exists():
        raise HTTPException(status_code=404, detail='混淆矩阵不存在')
    return FileResponse(path, media_type='image/png')
