#!/usr/bin/env bash
# scripts/start-backend.sh — 后端 (uvicorn) 手动控制脚本
#
# 设计意图 (按你的反馈 2026-07-27):
#   "我起码应该告诉我一下 + 我自己控制"
#   - 这个脚本是你启后端的"开关", 不依赖 systemd, 不依赖 docker
#   - 公司主机一般不会重启, 你不用操心自启
#   - 改后端代码 / 进程崩了 / 重启主机后, 用这个脚本手动 start 即可
#
# 用法:
#   bash scripts/start-backend.sh start     # 启 (后台 nohup)
#   bash scripts/start-backend.sh stop      # 停 (按 pid 文件)
#   bash scripts/start-backend.sh restart   # 重启
#   bash scripts/start-backend.sh status    # 看进程 + healthz
#   bash scripts/start-backend.sh logs      # tail -f 后端日志
#
# 它在哪:
#   - 进程: python3.8 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
#   - 工作目录: backend/
#   - 日志:    logs/backend.log
#   - PID 文件: /tmp/review-backend.pid

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
LOGS_DIR="$PROJECT_ROOT/logs"
BACKEND_PID_FILE="/tmp/review-backend.pid"
BACKEND_LOG="$LOGS_DIR/backend.log"
BACKEND_PORT="${REVIEW_BACKEND_PORT:-8000}"

mkdir -p "$LOGS_DIR"

log()  { printf '\033[1;34m[start-backend]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[start-backend]\033[0m %s\n' "$*" >&2; }

start() {
    if [ -f "$BACKEND_PID_FILE" ] && kill -0 "$(cat "$BACKEND_PID_FILE")" 2>/dev/null; then
        warn "backend 已经启动了, pid=$(cat "$BACKEND_PID_FILE")"
        warn "    想重启? 跑: bash scripts/start-backend.sh restart"
        return 0
    fi
    log "启动后端 (uvicorn :$BACKEND_PORT)"
    cd "$BACKEND_DIR"
    nohup python3.8 -m uvicorn app.main:app --host 0.0.0.0 --port "$BACKEND_PORT" \
        >> "$BACKEND_LOG" 2>&1 &
    echo $! > "$BACKEND_PID_FILE"
    sleep 1

    # 等健康
    local i=0
    while [ $i -lt 15 ]; do
        if curl --noproxy '*' -fsS -m 2 "http://localhost:$BACKEND_PORT/healthz" >/dev/null 2>&1; then
            log "已起来 (pid=$(cat "$BACKEND_PID_FILE"), /healthz = 200)"
            return 0
        fi
        sleep 1
        i=$((i+1))
    done
    warn "15s 内未 healthy, 看日志:"
    tail -n 20 "$BACKEND_LOG" >&2 || true
}

stop() {
    if [ ! -f "$BACKEND_PID_FILE" ]; then
        log "没 pid 文件, 不用停"
        return 0
    fi
    local pid
    pid=$(cat "$BACKEND_PID_FILE")
    if kill -0 "$pid" 2>/dev/null; then
        log "停后端 (pid $pid)"
        kill "$pid" 2>/dev/null || true
        sleep 1
        if kill -0 "$pid" 2>/dev/null; then
            warn "正常 SIGTERM 没退, 用 SIGKILL"
            kill -9 "$pid" 2>/dev/null || true
        fi
        log "已停"
    else
        warn "pid $pid 进程不在了, 清掉 pid 文件"
    fi
    rm -f "$BACKEND_PID_FILE"
}

restart() {
    stop || true
    start
}

status() {
    log "后端状态"
    if [ -f "$BACKEND_PID_FILE" ] && kill -0 "$(cat "$BACKEND_PID_FILE")" 2>/dev/null; then
        local pid
        pid=$(cat "$BACKEND_PID_FILE")
        local code
        code=$(curl --noproxy '*' -sS -o /dev/null -w '%{http_code}' -m 2 "http://localhost:$BACKEND_PORT/healthz" 2>/dev/null || echo "000")
        echo "  进程:  $pid  (uvicorn :$BACKEND_PORT)"
        echo "  健康:  HTTP $code  (GET /healthz)"
    else
        echo "  进程:  没在跑"
        echo "  启:    bash scripts/start-backend.sh start"
    fi
}

logs() {
    if [ -f "$BACKEND_LOG" ]; then
        tail -n 100 -f "$BACKEND_LOG"
    else
        warn "日志文件还没生成 (后端没启过?)"
    fi
}

case "${1:-start}" in
    start)    start ;;
    stop)     stop ;;
    restart)  restart ;;
    status)   status ;;
    logs)     logs ;;
    *)        echo "用法: $0 {start|stop|restart|status|logs}"; exit 1 ;;
esac
