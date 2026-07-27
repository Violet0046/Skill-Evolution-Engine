#!/usr/bin/env bash
# scripts/start-host.sh — 前端容器 (review-frontend-host) 手动控制
#
# 设计意图 (按你的反馈 2026-07-27):
#   - 前端跑在公司内网镜像起的 nginx 容器里, 自动 unless-stopped
#   - 但改前端代码后需要 rebuild dist + 重 build 镜像 + 重启容器, 这里给你一行
#   - 后端的 start/stop 不在这, 见 scripts/start-backend.sh
#
# 用法:
#   bash scripts/start-host.sh start     # 启容器 (build image if needed)
#   bash scripts/start-host.sh stop      # 停容器 (保留 image)
#   bash scripts/start-host.sh restart   # 重起容器 (用现有 image)
#   bash scripts/start-host.sh rebuild   # 重 build dist + image + 重起 (改前端 src 后用)
#   bash scripts/start-host.sh status    # 看容器状态
#   bash scripts/start-host.sh logs      # tail nginx 容器日志
#
# 关键概念 (你不改也行, 但出事要知道):
#   - dist/        frontend 的 vite build 产物, 在 host 上生成, COPY 进容器
#   - 容器内 nginx listen 5180, host 通过 docker -p 把端口透传出去
#   - 反代 /api/* 到 host 的 172.17.0.1:8000 (host docker0 网关 IP)
#     让后端是 host 上的 uvicorn 进程
#
# 改前端代码流程:
#   1. 编辑 frontend/src/**.tsx
#   2. cd frontend && ./node_modules/.bin/vite build          # 出新 dist/
#   3. cd .. && bash scripts/start-host.sh rebuild           # 镜像新化 + 重起

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
FRONTEND_DIR="$PROJECT_ROOT/frontend"
LOGS_DIR="$PROJECT_ROOT/logs"

HOST_PORT="${REVIEW_HOST_PORT:-5180}"
FRONTEND_CONTAINER="${REVIEW_FRONTEND:-review-frontend-host}"
FRONTEND_IMAGE="${REVIEW_FRONTEND_IMAGE:-review-frontend:host}"
BASE_IMAGE="aurora-release-docker.artnj.zte.com.cn/arch_metric/aes/aes-measure-base:v3"

mkdir -p "$LOGS_DIR"
log()  { printf '\033[1;34m[start-host]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[start-host]\033[0m %s\n' "$*" >&2; }

ensure_image() {
    if docker images --format '{{.Repository}}:{{.Tag}}' | grep -qx "$FRONTEND_IMAGE"; then
        log "已有镜像 $FRONTEND_IMAGE (跳过 build)"
        return 0
    fi
    build_image
}

build_image() {
    if [ ! -f "$FRONTEND_DIR/dist/index.html" ]; then
        log "dist/ 还没生成, 先 vite build"
        (cd "$FRONTEND_DIR" && ./node_modules/.bin/vite build)
    fi
    log "build 镜像 $FRONTEND_IMAGE (基于 $BASE_IMAGE)"
    docker build -f "$FRONTEND_DIR/Dockerfile.host" -t "$FRONTEND_IMAGE" "$FRONTEND_DIR"
}

run_container() {
    if docker ps -a --format '{{.Names}}' | grep -qx "$FRONTEND_CONTAINER"; then
        docker rm -f "$FRONTEND_CONTAINER" >/dev/null
    fi
    log "起容器 $FRONTEND_CONTAINER (host:$HOST_PORT -> nginx:$HOST_PORT)"
    docker run -d \
        --name "$FRONTEND_CONTAINER" \
        --hostname "review-frontend" \
        -p "${HOST_PORT}:5180" \
        --restart unless-stopped \
        "$FRONTEND_IMAGE"
    sleep 2
    # 探一下 / 确认
    local code
    code=$(curl --noproxy '*' -sS -o /dev/null -w '%{http_code}' -m 5 "http://localhost:${HOST_PORT}/" || echo "000")
    case "$code" in
        200) log "前端起来了 -> http://localhost:${HOST_PORT}/" ;;
        *)   warn "前端 HTTP $code (容器已起, 看 logs 排查)" ;;
    esac
}

start() {
    ensure_image
    run_container
}

stop() {
    if docker ps -a --format '{{.Names}}' | grep -qx "$FRONTEND_CONTAINER"; then
        log "停容器 $FRONTEND_CONTAINER"
        docker rm -f "$FRONTEND_CONTAINER" >/dev/null
    else
        log "容器 $FRONTEND_CONTAINER 没在跑"
    fi
}

restart() {
    # 不重 build, 用现有 image 重起
    if docker images --format '{{.Repository}}:{{.Tag}}' | grep -qx "$FRONTEND_IMAGE"; then
        run_container
    else
        warn "没有镜像 $FRONTEND_IMAGE, 走 build 流程"
        start
    fi
}

rebuild() {
    log "rebuild dist/ + 镜像 + 重起"
    (cd "$FRONTEND_DIR" && ./node_modules/.bin/vite build)
    docker rmi -f "$FRONTEND_IMAGE" 2>/dev/null || true
    build_image
    run_container
}

status() {
    log "前端容器状态"
    docker ps -a --filter "name=$FRONTEND_CONTAINER" --format "  {{.Names}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || true
    echo ""
    log "镜像"
    docker images --format "  {{.Repository}}:{{.Tag}}\t{{.Size}}" "$FRONTEND_IMAGE" 2>/dev/null || echo "  (没有)"
    echo ""
    log "dist 内容"
    ls -la "$FRONTEND_DIR/dist/" 2>/dev/null | sed 's/^/  /' || echo "  (没有)"
}

logs() {
    if docker ps -a --format '{{.Names}}' | grep -qx "$FRONTEND_CONTAINER"; then
        docker logs -f --tail=100 "$FRONTEND_CONTAINER"
    else
        warn "容器 $FRONTEND_CONTAINER 没在跑"
    fi
}

case "${1:-start}" in
    start)    start ;;
    stop)     stop ;;
    restart)  restart ;;
    rebuild)  rebuild ;;
    status)   status ;;
    logs)     logs ;;
    *)        echo "用法: $0 {start|stop|restart|rebuild|status|logs}"; exit 1 ;;
esac
