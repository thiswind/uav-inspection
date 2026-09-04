"""第二阶段素材上传：按 02-data 交付口径分类灌入数据目录（/data）。

供学生把摘除外置的视频/模型/测量数据经页面上传，替代手工配目录。
- 分类白名单映射到 02-data 的目标子目录，未知分类 422；
- 文件名取 basename、清洗控制字符，拒绝对抗性名字；
- 子目录可选（如 measurement_data 下的任务名），逐段校验防穿越；
- 默认拒绝覆盖已有文件（与交付 README「重名不要直接覆盖」一致），overwrite=true 显式放行；
- 大文件走分片上传（/upload/init → /upload/chunk ×N → /upload/complete），
  支持断点续传（/upload/status 查已收分片）与秒传（同名同大小直接命中），
  单片体积经 UAV_CHUNK_SIZE 环境变量可调（测试里调小以模拟大文件）。
"""
from __future__ import annotations

import json
import os
import re
import shutil
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from deployment_paths import DATA_ROOT

router = APIRouter()

CHUNK_SIZE = int(os.environ.get('UAV_CHUNK_SIZE', 8 * 1024 * 1024))

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
    # 展示用相对路径，不暴露服务器绝对路径
    try:
        display_root = str(scope.relative_to(DATA_ROOT))
    except ValueError:
        display_root = scope.name
    return {'code': 200, 'data': {'root': display_root, 'count': len(files), 'files': files}}


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


# ---------- 分片上传（大文件 / 断点续传 / 秒传） ----------

def _temp_root() -> Path:
    root = DATA_ROOT / '.upload-tmp'
    root.mkdir(parents=True, exist_ok=True)
    return root


def _upload_dir(upload_id: str) -> Path:
    if not re.fullmatch(r'[0-9a-f]{32}', upload_id or ''):
        raise HTTPException(status_code=422, detail='非法 uploadId')
    return _temp_root() / upload_id


def _part_index(path: Path) -> int:
    return int(path.stem)


@router.post('/upload/init')
async def upload_init(
    category: str = Form(...),
    filename: str = Form(...),
    size: int = Form(...),
    subdir: str = Form(''),
    overwrite: bool = Form(False),
):
    base = CATEGORIES.get(category)
    if base is None:
        raise HTTPException(status_code=422, detail=f'未知分类：{category}')
    if size <= 0:
        raise HTTPException(status_code=422, detail='size 必须为正')
    name = _safe_name(filename)
    target_dir = base / _safe_subdir(subdir)
    destination = target_dir / name

    # 秒传：同名同大小且不覆盖，直接命中
    if destination.exists() and destination.stat().st_size == size and not overwrite:
        return {'code': 200, 'data': {'mode': 'instant', 'path': str(destination), 'size': size}}

    upload_id = uuid.uuid4().hex
    workdir = _upload_dir(upload_id)
    workdir.mkdir(parents=True, exist_ok=True)
    meta = {
        'category': category,
        'subdir': subdir,
        'filename': name,
        'size': size,
        'overwrite': overwrite,
        'chunk_size': CHUNK_SIZE,
    }
    (workdir / 'meta.json').write_text(json.dumps(meta, ensure_ascii=False))
    total_chunks = (size + CHUNK_SIZE - 1) // CHUNK_SIZE

    # 顺手清理 7 天以上的废弃分片目录（合并失败/用户放弃的残留）
    now = time.time()
    for stale in _temp_root().iterdir():
        if stale.is_dir() and now - stale.stat().st_mtime > 7 * 86400:
            shutil.rmtree(stale, ignore_errors=True)

    return {'code': 200, 'data': {
        'mode': 'chunked', 'uploadId': upload_id, 'chunkSize': CHUNK_SIZE,
        'totalChunks': total_chunks, 'received': [],
    }}


@router.get('/upload/status')
async def upload_status(upload_id: str):
    workdir = _upload_dir(upload_id)
    if not workdir.is_dir():
        raise HTTPException(status_code=404, detail='uploadId 不存在（可能已合并或过期）')
    meta_path = workdir / 'meta.json'
    if not meta_path.is_file():
        raise HTTPException(status_code=404, detail='uploadId 不存在')
    meta = json.loads(meta_path.read_text())
    received = sorted(_part_index(p) for p in workdir.glob('*.part'))
    return {'code': 200, 'data': {
        'uploadId': upload_id,
        'received': received,
        # 回带分片参数：页面刷新后续传时前端无需重新 init，也避免服务端分片参数变更导致切片错位
        'chunkSize': meta['chunk_size'],
        'totalChunks': (meta['size'] + meta['chunk_size'] - 1) // meta['chunk_size'],
        'filename': meta['filename'],
    }}


@router.post('/upload/chunk')
async def upload_chunk(
    upload_id: str = Form(...),
    index: int = Form(...),
    file: UploadFile = File(...),
):
    workdir = _upload_dir(upload_id)
    meta_path = workdir / 'meta.json'
    if not meta_path.is_file():
        raise HTTPException(status_code=404, detail='uploadId 不存在')
    if index < 0:
        raise HTTPException(status_code=422, detail='非法分片号')
    meta = json.loads(meta_path.read_text())
    total_chunks = (meta['size'] + meta['chunk_size'] - 1) // meta['chunk_size']
    if index >= total_chunks:
        raise HTTPException(status_code=422, detail=f'分片号越界（共 {total_chunks} 片）')
    part = workdir / f'{index}.part'
    # 同分片重传（断点续传重试）幂等：直接覆盖
    with part.open('wb') as buffer:
        shutil.copyfileobj(file.file, buffer)
    await file.close()
    received = sorted(_part_index(p) for p in workdir.glob('*.part'))
    return {'code': 200, 'data': {'index': index, 'size': part.stat().st_size, 'received': received}}


@router.post('/upload/complete')
async def upload_complete(upload_id: str = Form(...)):
    workdir = _upload_dir(upload_id)
    meta_path = workdir / 'meta.json'
    if not meta_path.is_file():
        raise HTTPException(status_code=404, detail='uploadId 不存在')
    meta = json.loads(meta_path.read_text())
    base = CATEGORIES.get(meta['category'])
    target_dir = base / _safe_subdir(meta['subdir'])
    target_dir.mkdir(parents=True, exist_ok=True)
    destination = target_dir / meta['filename']

    size = meta['size']
    chunk_size = meta['chunk_size']
    total_chunks = (size + chunk_size - 1) // chunk_size
    parts = sorted(workdir.glob('*.part'), key=_part_index)
    indexes = [_part_index(p) for p in parts]
    if indexes != list(range(total_chunks)):
        missing = sorted(set(range(total_chunks)) - set(indexes))
        raise HTTPException(status_code=409, detail=f'分片不全，缺 {len(missing)} 片（续传请调 /upload/status）')

    # 校验总大小后原子合并（先写临时名再 rename，防半文件）
    total = sum(p.stat().st_size for p in parts)
    if total != size:
        raise HTTPException(status_code=409, detail=f'分片总大小 {total} ≠ 声明 {size}')
    if destination.exists() and not meta['overwrite']:
        shutil.rmtree(workdir, ignore_errors=True)
        return {'code': 200, 'data': {'path': str(destination), 'size': destination.stat().st_size,
                                      'deduplicated': '已存在同名文件（未开启覆盖），分片已清理'}}
    tmp_target = destination.with_name(destination.name + '.uploading')
    with tmp_target.open('wb') as out:
        for part in parts:
            with part.open('rb') as src:
                shutil.copyfileobj(src, out)
    tmp_target.replace(destination)
    shutil.rmtree(workdir, ignore_errors=True)
    return {'code': 200, 'data': {'path': str(destination), 'size': destination.stat().st_size,
                                  'chunks': total_chunks}}
