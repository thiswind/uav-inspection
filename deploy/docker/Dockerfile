# syntax=docker/dockerfile:1
# 无人机巡检系统 — 单容器镜像（FastAPI 8002 同源托管前端 dist + API + WebSocket）
# 构建上下文：仓库根（app/ 源码树 + deploy/）
# 前端以 VITE_BASE=/uav/ 构建（nginx 子路径部署）；改前缀需同步改 Dockerfile/compose/nginx 片段

FROM node:22-bookworm-slim AS fe-build
WORKDIR /src
COPY app/uav-inspection-ui/package.json app/uav-inspection-ui/package-lock.json ./
RUN npm config set registry https://registry.npmmirror.com && npm ci --no-audit --no-fund
COPY app/uav-inspection-ui/ ./
ARG VITE_BASE=/
ENV VITE_BASE=${VITE_BASE}
RUN npm run build

FROM python:3.12-slim-bookworm AS runtime
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUTF8=1 \
    PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
WORKDIR /app
COPY app/uav-inspection-backend/requirements.txt app/uav-inspection-backend/requirements-base.txt \
     app/uav-inspection-backend/requirements-base-lock.txt /tmp/
# OpenCV 运行库与 pip 依赖同层（slim 缺 libxcb/libGL 会静默降级视觉功能）
RUN pip install --no-cache-dir -r /tmp/requirements.txt \
    && apt-get update -qq \
    && apt-get install -y -qq --no-install-recommends libxcb1 libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*
COPY app/uav-inspection-backend/ /app/uav-inspection-backend/
COPY --from=fe-build /src/dist /app/uav-inspection-ui/dist
# UAV_DATA_DIR 指向命名卷挂载点；UAV_URL_PREFIX 与 VITE_BASE 保持一致
# 布局镜像原交付包（backend 与 ui 同级），deployment_paths.py 按 parent.parent 推 PROJECT_ROOT=/app
ENV UAV_DATA_DIR=/data \
    YOLO_CONFIG_DIR=/data/.cache/ultralytics
EXPOSE 8002
WORKDIR /app/uav-inspection-backend
CMD ["python", "-m", "uvicorn", "heatmapapp.main:app", "--host", "0.0.0.0", "--port", "8002"]
