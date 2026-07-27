# Skill-Evolution-Review 部署手册

> 这份文档是给未来的你 / 接手的同事 / 半年后忘了怎么启动的自己看的。
> 看完按"快速启动"那一节就能跑。

## 1. 项目

评审系统：让评审员在浏览器里查阅 SEE（Skill Evolution Engine）流水线
产出的 changes、对照 diff、查看证据、提交 approve / modify / reject 决策。

## 2. 架构（生产形态）

```
                     公司内网 (10.90.213.38)
                              │
                              │  http://10.90.213.38:5180/
                              ▼
+---------------------------------------------------------+
| Linux 主机 (10.90.213.38)                              |
|                                                         |
|  +-------------------+    review-net (docker bridge)    |
|  | review-frontend   |    (容器互联)                     |
|  | (nginx:alpine)    |◄──────────┐                      |
|  | 监听容器:80       │           │                      |
|  | 映射 host:5180    │           │ backend:8000         |
|  +────────┬──────────+           │ (容器名解析)           |
|           │ /api/* 反代         │                       |
|           ▼                     │                       |
|  +-------------------+           │                       |
|  | review-backend    │───────────┘                       |
|  | (python:3.11)     │                                   |
|  | uvicorn :8000     │                                   |
|  +────────┬──────────+                                   |
|           │ PyMySQL                                      |
|           ▼                                              |
|  公司 MySQL (10.89.245.224:3306)                          |
|  database: knowledge_engineering                         |
+---------------------------------------------------------+
```

两个容器都在 host 上跑：

| 容器名 | 镜像 | 内部端口 | host 端口 | 重启策略 |
|---|---|---|---|---|
| `review-backend` | `review-backend:local` | 8000 | 不暴露 | unless-stopped |
| `review-frontend` | `review-frontend:local` | 80 | **5180** | unless-stopped |

端口选择说明：
- 80 已被公司 `dq_checker`（数据库质量检查的文件下载服务）占用，不能抢
- 选 5180 是 `5173` + 7 的偏移，避开常见 dev 端口、与 vite dev 默认端口不撞

## 3. 快速启动（3 步）

```bash
# 1. cd 到项目根目录
cd /home/10358563/.claude/agents/Skill-Evolution-Engine/Skill-Evolution-Review

# 2. 确认 .env 存在 (后端连公司 MySQL 的配置)
[ -f backend/.env ] || cp backend/.env.example backend/.env   # 没有示例就先不复制, 检查

# 3. 一键起
bash scripts/start.sh
```

起完后访问：
- **公司内网同事**：`http://10.90.213.38:5180/`
- **本机**：`http://localhost:5180/`

## 4. 常用命令

```bash
bash scripts/start.sh           # 起 (build + run + healthcheck)
bash scripts/start.sh stop      # 停
bash scripts/start.sh restart   # 重起 (改代码后常用)
bash scripts/start.sh status    # 看状态
bash scripts/start.sh logs      # 实时日志 (backend + frontend 一起)
bash scripts/start.sh cleanup   # 删容器 + 网络 + 镜像 (重建前用)
```

## 5. 文件清单

| 文件 | 作用 |
|---|---|
| `backend/` | FastAPI 后端代码 |
| `backend/Dockerfile` | 后端镜像构建 (基于 python:3.11-slim + uvicorn) |
| `backend/.env` | MySQL 连接配置 (被 .gitignore 忽略, 不进 git) |
| `backend/app/main.py` | FastAPI 入口 + CORS 白名单 |
| `frontend/` | React 前端代码 |
| `frontend/Dockerfile` | 多阶段: node build → nginx:alpine serve |
| `frontend/nginx.conf` | 容器内 nginx: serve dist + `/api/` 反代到 backend |
| `docker-compose.yml` | docker compose v2 用户的快速路径（**本机不可用**，但机器装好的人能直接 `docker compose up`） |
| `scripts/start.sh` | **本机主路径**，把 docker-compose.yml 的功能用 `docker run` 实现 |
| `DEPLOY.md` | 本文件 |

## 6. 改代码后的发布流程

1. **改了 frontend**：跑 `bash scripts/start.sh restart`（会重新 build 镜像）
2. **改了 backend**：跑 `bash scripts/start.sh restart`
3. **同时改**：同上

build 是冷启动会缓存，没改的阶段不会重 build；如果发现 build 卡住或行为可疑：

```bash
bash scripts/start.sh cleanup   # 删干净
bash scripts/start.sh start     # 全量重建
```

## 7. 故障排查

### 7.1 启动失败常见原因

| 现象 | 原因 | 修法 |
|---|---|---|
| `Cannot connect to the Docker daemon` | dockerd 没跑 | `sudo systemctl start docker` |
| `port is already allocated` | 5180 被占 | `lsof -i :5180` 找谁占着，杀掉或改 `REVIEW_HOST_PORT` 启 |
| backend 起来 30s 内 unhealthy | 公司 MySQL 不通 | 在 host 上 `mysql -h 10.89.245.224 -u knowledge_user -p` 试一下；不通就找 DBA |
| `permission denied while trying to connect to the Docker daemon socket` | 当前用户不在 docker 组 | `sudo usermod -aG docker $USER`，**重新登录** |

### 7.2 公司同事访问不到

```bash
# 1. 容器在跑吗?
docker ps --filter "name=review-frontend" --format "{{.Names}}\t{{.Status}}"

# 2. host 端口在监听吗?
ss -tlnp | grep 5180

# 3. firewall 开了吗?
sudo firewall-cmd --list-ports 2>/dev/null || sudo iptables -L -n | grep 5180

# 4. 直接从别的机器 curl 测一下
curl -v http://10.90.213.38:5180/api/runs
```

### 7.3 容器起不来，瞬崩

```bash
docker logs --tail=200 review-backend
docker logs --tail=200 review-frontend
```

后端常见：
- `ModuleNotFoundError`: pyproject.toml 改了但没装；`cleanup` 后重 build
- `Can't connect to MySQL`: 网络或认证失败
- `address already in use`: 容器内有别的进程占着 8000（很少见）

前端常见：
- `/usr/share/nginx/html/index.html: not found`: build 失败，回看 build log
- `502 Bad Gateway` 来自前端到 backend: backend 没起来或 healthcheck 没通过

### 7.4 改代码后页面没更新

Vite build 出来的 assets 是 hashed 文件名（`index-abc123.js`），改了源码
build 出来新 hash，**浏览器缓存**会用老的 hash。需要：

- **自己**：硬刷 `Ctrl+Shift+R`
- **同事**：硬刷一次，或等着浏览器自然过期（默认不强缓存 index.html）

## 8. 端口 / CORS

后端 `main.py` 当前的 CORS 白名单：

```python
allow_origins=[
    # dev
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    # 部署后
    "http://10.90.213.38:5180",
    "http://10.90.213.38",
    "http://localhost:5180",
    "http://127.0.0.1:5180",
],
```

注意：生产用 nginx 反代后，**前端和后端是同源**（同 `http://10.90.213.38:5180`），
CORS 在浏览器侧就不会触发。CORS 白名单主要是给"绕开 nginx"和"开发模式"留口子。

如果 host 改端口或 IP 变了，**同步**改 `backend/app/main.py` 这两行。

## 9. 同事访问的是哪个 URL

唯一合法入口：**`http://10.90.213.38:5180/`**

不要让同事用：
- `http://10.90.213.38:8000/`（后端没暴露到 host）
- `http://10.90.213.38/`（80 端口是 dq_checker，文件下载服务）

## 10. 想用 docker compose（如果未来装上了）

```bash
docker compose up -d --build
```

`docker-compose.yml` 已经写好，行为跟 `start.sh` 一致。装 compose 插件：

```bash
sudo dnf install docker-compose-plugin
# 或者手动二进制 (公司网络可能不通):
# https://github.com/docker/compose/releases
```

## 11. 长期运行 / 离职交接

容器重启策略是 `unless-stopped`：主机重启后容器会自己起来。

**主机完全重装怎么办**？步骤：
1. `git clone`（或拷贝整个项目目录）
2. 复刻 `backend/.env`（MySQL 凭据；.gitignore 不进 git，要从密码管理器找）
3. `bash scripts/start.sh`

只要 docker 还在、公司 MySQL 还在、port 5180 没被其它服务抢，**5 分钟内** 同事又能在 `http://10.90.213.38:5180/` 继续评审。
