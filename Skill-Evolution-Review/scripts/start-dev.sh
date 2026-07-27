#!/usr/bin/env bash
# =============================================================================
# start-dev.sh — 一键起 Skill-Evolution-Review 的 backend + frontend
#
# 用法:
#   bash scripts/start-dev.sh
#
# 行为:
#   - 后端: 用 infra/scripts/with-python.sh 跑 uvicorn (启在 8000)
#   - 前端: 用 npm 跑 vite dev      (启在 5173)
#   - 日志: stdout 加 [backend] / [frontend] 前缀, 写到 logs/start-dev.log
#   - 关闭: 任意一处 Ctrl+C → 同时停两个服务
#
# 端口占用:
#   后端 8000,  前端 5173  ← 改这里调整
# =============================================================================

set -uo pipefail

# ---------- 路径自定位 ----------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKEND_DIR="$ROOT/backend"
FRONTEND_DIR="$ROOT/frontend"
SEE_REPO="$(cd "$ROOT/.." && pwd)"   # Skill-Evolution-Engine 仓库根
PYTHON_SH="$SEE_REPO/infra/scripts/with-python.sh"

# 校验文件存在, 避免沉默失败
for p in "$BACKEND_DIR/app/main.py" "$FRONTEND_DIR/package.json" "$PYTHON_SH"; do
    [ -e "$p" ] || { echo "ERROR: 找不到 $p" >&2; exit 1; }
done

# ---------- 配置 ----------
LOG_DIR="$ROOT/logs"
LOG_FILE="$LOG_DIR/start-dev.log"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"

mkdir -p "$LOG_DIR"

echo "[$(date '+%H:%M:%S')] starting (logs -> $LOG_FILE)"
echo "  backend  → http://localhost:$BACKEND_PORT"
echo "  frontend → http://localhost:$FRONTEND_PORT"
echo "  按 Ctrl+C 退出"

# ---------- 启动子进程 ----------
# setsid 让两个子进程脱离当前进程组, 避免 Ctrl+C 只杀父 bash 不杀子的尴尬
# (我们额外用 PIDs 数组 + kill trap 收尾)

BACKEND_LOG="$LOG_DIR/backend.log"
FRONTEND_LOG="$LOG_DIR/frontend.log"
: > "$BACKEND_LOG"
: > "$FRONTEND_LOG"

# 后端
setsid bash -c "exec $PYTHON_SH -m uvicorn --app-dir '$BACKEND_DIR' app.main:app --reload --port $BACKEND_PORT --host 127.0.0.1" \
    > "$BACKEND_LOG" 2>&1 &
BACKEND_PID=$!

# 前端 (Vite 配置里 host=0.0.0.0 但 dev 默认绑 localhost)
cd "$FRONTEND_DIR"
setsid bash -c "exec npm run dev -- --host 127.0.0.1 --port $FRONTEND_PORT" \
    > "$FRONTEND_LOG" 2>&1 &
FRONTEND_PID=$!
cd - > /dev/null

echo "  backend PID  = $BACKEND_PID  (log: $BACKEND_LOG)"
echo "  frontend PID = $FRONTEND_PID (log: $FRONTEND_LOG)"

# ---------- 关停处理 ----------
_CLEANED=0
cleanup() {
    # EXIT trap 跟 INT trap 串行触发, 用 _CLEANED 保证只跑一次 cleanup
    [ "$_CLEANED" = "1" ] && return
    _CLEANED=1
    echo ""
    echo "[$(date '+%H:%M:%S')] shutting down..."
    kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
    sleep 1
    kill -9 "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
    echo "[$(date '+%H:%M:%S')] stopped."
}
trap cleanup INT TERM EXIT

# ---------- 持续打印两个服务的 stdout ----------
# 每 1.5s 把两个 log 增量输出, 标 [backend]/[frontend]
LAST_B=0
LAST_F=0
TICK=0
while kill -0 "$BACKEND_PID" 2>/dev/null && kill -0 "$FRONTEND_PID" 2>/dev/null; do
    sleep 1.5
    TICK=$((TICK+1))

    # 后端
    if [ -f "$BACKEND_LOG" ]; then
        CUR=$(stat -c '%s' "$BACKEND_LOG" 2>/dev/null || echo 0)
        if [ "$CUR" -gt "$LAST_B" ]; then
            tail -c +$((LAST_B+1)) "$BACKEND_LOG" | sed 's/^/[backend] /'
            LAST_B=$CUR
        fi
    fi
    # 前端
    if [ -f "$FRONTEND_LOG" ]; then
        CUR=$(stat -c '%s' "$FRONTEND_LOG" 2>/dev/null || echo 0)
        if [ "$CUR" -gt "$LAST_F" ]; then
            tail -c +$((LAST_F+1)) "$FRONTEND_LOG" | sed 's/^/[frontend] /'
            LAST_F=$CUR
        fi
    fi
done

# 任何一个挂了 → 走到这里
echo "[$(date '+%H:%M:%S')] 一个服务已退出, 准备 cleanup"
cleanup
