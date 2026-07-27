# scripts/

## 全部就这两个脚本

| 脚本 | 管什么 |
|---|---|
| [`start-backend.sh`](start-backend.sh) | **后端** Python 进程 (uvicorn, host 上跑) |
| [`start-host.sh`](start-host.sh) | **前端** docker 容器 (nginx, 监听 host:5180) |

数据库在公司 MySQL (`10.89.245.224`)，不在本机，不要管。

---

## 速查

### 后端 (uvicorn)

```bash
bash scripts/start-backend.sh start     # 启
bash scripts/start-backend.sh stop      # 停
bash scripts/start-backend.sh restart   # 改代码后重起
bash scripts/start-backend.sh status    # 看状态
bash scripts/start-backend.sh logs      # tail -f 日志
```

进程在 `pid /tmp/review-backend.pid`，日志在 `../logs/backend.log`。

### 前端 (nginx 容器)

```bash
bash scripts/start-host.sh start        # 启 (有 image 就直接起, 没就 build)
bash scripts/start-host.sh stop         # 停容器
bash scripts/start-host.sh restart      # 重起容器 (用现有 image)
bash scripts/start-host.sh rebuild      # 改前端代码后用: 重 build dist + 重 build 镜像 + 重起
bash scripts/start-host.sh status       # 看容器 / 镜像 / dist
bash scripts/start-host.sh logs         # tail 容器日志
```

容器名 `review-frontend-host`，镜像 `review-frontend:host`。

---

## 改代码流程

| 你改了 | 跑这一行 |
|---|---|
| 后端 `backend/app/**.py` | `bash scripts/start-backend.sh restart` |
| 前端 `frontend/src/**.{ts,tsx,css}` 或 `frontend/vite.config.ts` | `bash scripts/start-host.sh rebuild` |
| 前端 `frontend/Dockerfile.host` 或 `frontend/nginx.host.conf` 或 `frontend/nginx.conf.host` | `bash scripts/start-host.sh rebuild` |
| 数据库 schema (`infra/core/review_db/ddl/...sql`) | 见 SEE 上游流水线，不归本仓库管 |

---

## 详尽文档

- `../DOCKER.md` — 前端容器怎么进 / 代码在哪 / 怎么推
- `../DEPLOY.md` — 端口 / URL / 公司内网 / 故障排查

---

## 备注

- 之前有 `start.sh` / `start-dev.sh` / `kill-dev.sh` / `review-backend.service`，全删了。
  - `start-dev.sh` 是开发模式（vite dev + uvicorn --reload），开发完了用不上
  - `start.sh` 是未来"双容器"蓝图，依赖公司没有的镜像源
  - `review-backend.service` 是 systemd service，你机器上跑不起来（USER 217 错），不折腾
- 不需要看历史，直接用上面两个就够
