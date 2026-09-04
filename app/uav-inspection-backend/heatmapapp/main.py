import os
import importlib.util
from pathlib import Path
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from deployment_paths import DATA_ROOT, PROJECT_ROOT, backend_path, project_path

from heatmapapp.api.v1 import tasks, websocket, predict
from heatmapapp.services.ai_inference import engine
from pestapp.api.endpoints import pest as pest_router
from pestapp.api.endpoints import ws_agent, ws_logs, ws_telemetry
from roseapp.api import detect as rose_detect
from telecomapp.api import detect as telecom_detect
from roofapp.api import detect as roof_detect
from powerapp.api import detect as power_detect
from wallapp.api import detect as wall_detect
from treeapp.api import detect as pruning_detect
from vegetationapp import api as vegetation_api
from assetsapp import api as assets_api

app = FastAPI(title='园区无人机巡检系统')

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=False,
    allow_methods=['*'],
    allow_headers=['*'],
)

VIDEO_PATH = backend_path('heatmapdata', 'videos')
SNAPSHOT_PATH = backend_path('heatmapdata', 'snapshots')
PEST_MEDIA_PATH = backend_path('pestdata', 'media')
ROSE_TASKS_PATH = backend_path('rose-tasks')
TELECOM_MEDIA_PATH = backend_path('telecomdata', 'media')
TELECOM_TASKS_PATH = backend_path('telecom-tasks')
ROOF_MEDIA_PATH = backend_path('roofdata', 'media')
ROOF_REPORTS_PATH = backend_path('roofdata', 'reports')
POWER_MEDIA_PATH = backend_path('powerdata', 'media')
WALL_MEDIA_PATH = backend_path('walldata', 'media')
PRUNING_MEDIA_PATH = backend_path('treedata', 'media')
ROSE_PICTURES_PATH = project_path('uav-inspection-ui', 'public', 'rose-pictures')
FRONTEND_DIST = Path(os.getenv('UAV_FRONTEND_DIST', str(PROJECT_ROOT / 'uav-inspection-ui' / 'dist'))).resolve()

for path in [VIDEO_PATH, SNAPSHOT_PATH, PEST_MEDIA_PATH, ROSE_TASKS_PATH, TELECOM_MEDIA_PATH, TELECOM_TASKS_PATH, ROOF_MEDIA_PATH, ROOF_REPORTS_PATH, POWER_MEDIA_PATH, WALL_MEDIA_PATH, PRUNING_MEDIA_PATH, ROSE_PICTURES_PATH]:
    os.makedirs(path, exist_ok=True)

app.include_router(tasks.router, prefix='/api/v1/tasks', tags=['任务'])
app.include_router(websocket.router, prefix='/api/v1/ws', tags=['实时推理'])
app.include_router(predict.router, prefix='/api/v1/predict', tags=['客流预测'])
app.include_router(pest_router.router, prefix='/api/v1/pest', tags=['病虫害巡检'])
app.include_router(rose_detect.router, prefix='/api/v1/rose', tags=['玫瑰检测'])
app.include_router(telecom_detect.router, prefix='/api/v1/telecom', tags=['通信基站巡检'])
app.include_router(roof_detect.router, prefix='/api/v1/roof', tags=['屋顶巡检'])
app.include_router(power_detect.router, prefix='/api/v1/power', tags=['杆路线路巡检'])
app.include_router(wall_detect.router, prefix='/api/v1/wall', tags=['建筑外墙巡检'])
app.include_router(pruning_detect.router, prefix='/api/v1/pruning', tags=['乔木修剪检测'])
app.include_router(vegetation_api.router, prefix='/api/v1/vegetation', tags=['乔木与绿化测量'])
app.include_router(assets_api.router, prefix='/api/v1/assets', tags=['素材上传'])

app.mount('/api/v1/pest/media', StaticFiles(directory=PEST_MEDIA_PATH), name='pest_media')
app.mount('/api/v1/rose/tasks', StaticFiles(directory=ROSE_TASKS_PATH), name='rose_tasks')
app.mount('/api/v1/media', StaticFiles(directory=VIDEO_PATH), name='media')
app.mount('/api/v1/snapshots', StaticFiles(directory=SNAPSHOT_PATH), name='snapshots')
app.mount('/api/v1/telecom/media', StaticFiles(directory=TELECOM_MEDIA_PATH), name='telecom_media')
app.mount('/api/v1/telecom/tasks', StaticFiles(directory=TELECOM_TASKS_PATH), name='telecom_tasks')
app.mount('/api/v1/roof/media', StaticFiles(directory=ROOF_MEDIA_PATH), name='roof_media')
app.mount('/api/v1/roof/reports', StaticFiles(directory=ROOF_REPORTS_PATH), name='roof_reports')
app.mount('/api/v1/power/media', StaticFiles(directory=POWER_MEDIA_PATH), name='power_media')
app.mount('/api/v1/wall/media', StaticFiles(directory=WALL_MEDIA_PATH), name='wall_media')
app.mount('/api/v1/pruning/media', StaticFiles(directory=PRUNING_MEDIA_PATH), name='pruning_media')
app.mount('/rose-pictures', StaticFiles(directory=ROSE_PICTURES_PATH), name='rose_pictures')

app.include_router(ws_agent.router, prefix='/ws/v1', tags=['Agent对话'])
app.include_router(ws_logs.router, prefix='/ws/v1', tags=['系统日志'])
app.include_router(ws_telemetry.router, prefix='/ws/v1', tags=['遥测数据流'])


@app.get('/')
async def root():
    if (FRONTEND_DIST / 'index.html').is_file():
        return FileResponse(FRONTEND_DIST / 'index.html')
    return {'status': 'running', 'api_docs': '/docs'}


@app.get('/api/health')
async def health():
    return {'status': 'ok'}


@app.get('/api/deployment/status')
async def deployment_status():
    weight_files = {
        'heatmap': backend_path('heatmapweight', 'renliu.pt'),
        'rose': Path(os.getenv('ROSE_MODEL_PATH', str(backend_path('roseapp', 'rose-detect-best.pt')))),
        'telecom': backend_path('telecomapp', 'station2-best.pt'),
        'power': backend_path('powerapp', 'wire-pole-seg.pt'),
        'wall': backend_path('wallapp', 'wall-damage-best.pt'),
        'pruning': backend_path('treeapp', 'tree-pruning-best.pt'),
    }
    models = {name: path.is_file() for name, path in weight_files.items()}
    dependencies = all(importlib.util.find_spec(name) is not None for name in ('torch', 'ultralytics'))
    media_roots = [VIDEO_PATH, PEST_MEDIA_PATH, ROSE_TASKS_PATH, TELECOM_MEDIA_PATH,
                   TELECOM_TASKS_PATH, ROOF_MEDIA_PATH, POWER_MEDIA_PATH, WALL_MEDIA_PATH, PRUNING_MEDIA_PATH]
    media_suffixes = {'.mp4', '.avi', '.mov', '.mkv', '.webm'}
    has_video = any(p.suffix.lower() in media_suffixes for folder in media_roots for p in folder.rglob('*') if p.is_file())
    has_measurements = any(project_path('measurement_data').glob('*/green_area_summary.json'))
    return {'code': 200, 'data': {
        'data_available': has_video or has_measurements,
        'inference_available': dependencies and any(models.values()),
        'inference_dependencies_installed': dependencies,
        'models': models,
        'missing_models': [name for name, exists in models.items() if not exists],
        'data_root': str(DATA_ROOT),
        'message': '未安装的数据和模型为可选项；基础服务可正常运行。',
    }}


@app.get('/api/video_feed/{task_id}')
async def video_feed(task_id: str):
    try:
        engine.ensure_model()
    except (FileNotFoundError, RuntimeError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return StreamingResponse(engine.run_stream(task_id), media_type='multipart/x-mixed-replace; boundary=frame')


@app.get('/api/current_stats')
async def get_current_stats():
    return {'code': 200, 'data': {}}


@app.get('/api/snapshot')
async def get_latest_snapshot():
    if not hasattr(engine, 'current_frame_bytes') or engine.current_frame_bytes is None:
        return Response(status_code=404, content='画面还没有准备好')
    return Response(content=engine.current_frame_bytes, media_type='image/jpeg')


@app.get('/{path:path}', include_in_schema=False)
async def frontend(path: str):
    # Resolve within dist; never expose source or turn an unknown API into HTML.
    if path.split('/', 1)[0] in {'api', 'ws'}:
        raise HTTPException(status_code=404, detail='接口不存在')
    candidate = (FRONTEND_DIST / path).resolve()
    if not candidate.is_relative_to(FRONTEND_DIST):
        raise HTTPException(status_code=404)
    if candidate.is_file():
        return FileResponse(candidate)
    spa_routes = {'telecom', 'pest', 'heatmap-flow', 'power', 'roof', 'wall', 'pruning',
                  'height', 'area', 'rose-digital', 'rose-yield', 'assets'}
    if path.strip('/') in spa_routes and (FRONTEND_DIST / 'index.html').is_file():
        return FileResponse(FRONTEND_DIST / 'index.html')
    raise HTTPException(status_code=404, detail='页面或文件不存在；首次部署请先运行 setup。')

