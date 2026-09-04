#!/usr/bin/env bash
# 服务器端：构建镜像并推送到自建 registry（在源码树根执行；REG 按现场替换）
set -euo pipefail
REG="${UAV_REGISTRY:-127.0.0.1:15000}"
IMAGE="$REG/uav/inspection"

echo "[build] 开始构建 $IMAGE:latest（首次构建较久，含前端 npm 与后端 pip；依赖层不变时走缓存分钟级）"
sudo docker build -f deploy/docker/Dockerfile --build-arg VITE_BASE="${VITE_BASE:-/uav/}" -t "$IMAGE:latest" .
echo "[build] 完成，推送到 registry"
sudo docker push "$IMAGE:latest"
echo "[build] $IMAGE:latest 已入库"
