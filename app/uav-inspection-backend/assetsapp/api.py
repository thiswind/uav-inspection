"""第二阶段素材上传：按 02-data 交付口径分类灌入数据目录（/data）。

供学生把摘除外置的视频/模型/测量数据经页面上传，替代手工配目录。
- 分类白名单映射到 02-data 的目标子目录，未知分类 422；
- 文件名取 basename、清洗控制字符，拒绝对抗性名字；
- 子目录可选（如 measurement_data 下的任务名），逐段校验防穿越；
- 默认拒绝覆盖已有文件（与交付 README「重名不要直接覆盖」一致），overwrite=true 显式放行。
"""
from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from deployment_paths import DATA_ROOT

router = APIRouter()

# 分类 → 02-data 内目标目录（uav-inspection-backend 下为各模块数据/模型根，project 级为测量与玫瑰图片）
CATEGORIES: dict[str, Path] = {
    'heatmap-videos': DATA_ROOT / 'uav-inspection-backend' / 'heatmapdata' / 'videos',
    'heatmap-model': DATA_ROOT / 'uav-inspection-backend' / 'heatmapweight',
    'telecom-media': DATA_ROOT / 'uav-inspection-backend' / 'telecomdata' / 'media',
    'power-media': DATA_ROOT / 'uav-inspection-backend' / 'powerdata' / 'media',
    'wall-media': DATA_ROOT / 'uav-inspection-backend' / 'walldata' / 'media',
    'roof-media': DATA_ROOT / 'uav-inspection-backend' / 'roofdata' / 'media',
    'pruning-media': DATA_ROOT / 'uav-inspection-backend' / 'treedata' / 'media',
    'rose-pictures': DATA_ROOT / 'uav-inspection-ui' / 'public' / 'rose-pictures',
    'measurement-data': DATA_ROOT / 'measurement_data',
    'models': DATA_ROOT / 'models',
}

FORBIDDEN_NAME = re.compile(r'[\x00-\x1f\x7f]')
SEGMENT = re.compile(r'^[^/\\\0]+$')

for _path in CATEGORIES.values():
    _path.mkdir(parents=True, exist_ok=True)


def _safe_subdir(raw: str | None) -> Path:
    parts = [p for p in (raw or '').replace('\\', '/').split('/') if p not in ('', '.')]
    for part in parts:
        if part == '..' or not SEGMENT.match(part):
            raise HTTPException(status_code=422, detail=f'非法子目录段：{part!r}')
    return Path(*parts) if parts else Path()


def _safe_name(raw: str | None) -> str:
    name = os.path.basename((raw or '').replace('\\', '/'))
    if not name or name in ('.', '..') or FORBIDDEN_NAME.search(name):
        raise HTTPException(status_code=422, detail='非法文件名')
    return name


@router.get('/categories')
async def list_categories():
    return {
        'code': 200,
        'data': [
            {
                'key': key,
                'label': label,
                'target': str(CATEGORIES[key].relative_to(DATA_ROOT)),
            }
            for key, label in (
                ('heatmap-videos', '客流热力视频（heatmapdata/videos）'),
                ('heatmap-model', '客流热力模型 renliu.pt（heatmapweight）'),
                ('telecom-media', '通信基站视频（telecomdata/media）'),
                ('power-media', '杆路线路视频（powerdata/media）'),
                ('wall-media', '建筑外墙视频（walldata/media）'),
                ('roof-media', '建筑屋顶视频（roofdata/media）'),
                ('pruning-media', '乔木修剪视频（treedata/media）'),
                ('rose-pictures', '玫瑰园照片（rose-pictures）'),
                ('measurement-data', '测量结果（measurement_data）'),
                ('models', '其他模型（models）'),
            )
        ],
    }


@router.get('/files')
async def list_files(category: str, subdir: str = ''):
    base = CATEGORIES.get(category)
    if base is None:
        raise HTTPException(status_code=422, detail=f'未知分类：{category}')
    scope = base / _safe_subdir(subdir)
    files = []
    for path in sorted(scope.rglob('*')):
        if path.is_file():
            stat = path.stat()
            files.append({
                'path': str(path.relative_to(base)),
                'size': stat.st_size,
                'modified': int(stat.st_mtime),
            })
    return {'code': 200, 'data': {'root': str(scope), 'count': len(files), 'files': files}}


@router.post('/upload')
async def upload_assets(
    category: str = Form(...),
    subdir: str = Form(''),
    overwrite: bool = Form(False),
    files: list[UploadFile] = File(...),
):
    base = CATEGORIES.get(category)
    if base is None:
        raise HTTPException(status_code=422, detail=f'未知分类：{category}')
    target_dir = base / _safe_subdir(subdir)
    target_dir.mkdir(parents=True, exist_ok=True)

    saved, skipped = [], []
    for item in files:
        name = _safe_name(item.filename)
        destination = target_dir / name
        if destination.exists() and not overwrite:
            skipped.append({'name': name, 'reason': '已存在（未开启覆盖）'})
            await item.close()
            continue
        with destination.open('wb') as buffer:
            shutil.copyfileobj(item.file, buffer)
        await item.close()
        saved.append({'name': name, 'size': destination.stat().st_size})

    return JSONResponse(status_code=200, content={
        'code': 200,
        'data': {
            'category': category,
            'dir': str(target_dir),
            'saved': saved,
            'skipped': skipped,
        },
    })
