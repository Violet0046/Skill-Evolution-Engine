#!/usr/bin/env bash
# kill-dev.sh — 应急: 手动杀 start-dev.sh 起的 uvicorn + vite
#
# 用法:
#   bash scripts/kill-dev.sh
#
# 仅本地开发期应急使用 (Ctrl+C 失灵 / 终端卡死 / 远程断开等).
# 生产部署不要用这个 → 用 docker-compose down / kubectl / systemctl.

set -uo pipefail

# 杀 Skill-Evolution-Review 范围内一切 python(uvicorn) + node(vite)
echo "stopping uvicorn..."
pkill -f "uvicorn --app-dir.*Skill-Evolution-Review/backend" 2>/dev/null && echo "  uvicorn killed" || echo "  (none)"
pkill -f "Skill-Evolution-Review/backend/app/main:app" 2>/dev/null
echo "stopping vite..."
pkill -f "vite" 2>/dev/null && echo "  vite killed" || echo "  (none)"
echo "done."
