#!/usr/bin/env bash
# 无人机巡检系统服务器端部署/运维脚本（在服务器 ~/workspace/uav-inspection/deploy 上执行）
# 用法：./deploy.sh up|update|down|status|logs
set -euo pipefail
cd "$(dirname "$0")"

ACTION="${1:-}"
[ -n "$ACTION" ] || { echo "用法: $0 up|update|down|status|logs"; exit 1; }

ensure_env() {
  if [ ! -f .env ]; then
    echo "[deploy] 缺 .env，从 .env.example 复制后重跑" >&2
    cp .env.example .env 2>/dev/null || true
    exit 1
  fi
}

case "$ACTION" in
  up)
    ensure_env
    sudo docker compose up -d
    sudo docker compose ps
    ;;
  update)
    ensure_env
    sudo docker compose pull 2>/dev/null || true
    sudo docker compose up -d
    sudo docker compose ps
    ;;
  down)
    sudo docker compose down
    ;;
  status)
    sudo docker compose ps
    ;;
  logs)
    sudo docker compose logs --tail=80 "${2:-}"
    ;;
  *)
    echo "未知动作: $ACTION" >&2; exit 1 ;;
esac
