# scripts/

## start-dev.sh — 一键起后端 + 前端

```bash
cd Skill-Evolution-Review
bash scripts/start-dev.sh
```

启起来后:
- 后端 8000 (uvicorn)
- 前端 5173 (vite)
- 按 Ctrl+C 同时停

日志写到 `logs/start-dev.log` + 同时 `logs/backend.log` / `logs/frontend.log`.

如果 npm 第一次跑没装依赖: 自己 `cd frontend && npm install` 一次.

## kill-dev.sh — 应急手动杀

```bash
bash scripts/kill-dev.sh
```

Ctrl+C 失灵或 terminal 卡死时使用. 平时不要跑.

## 生产部署

不用这套脚本. 改用:
- Docker Compose: `docker compose down`
- Kubernetes: `kubectl delete deployment`
- systemd: `systemctl stop review-system`
