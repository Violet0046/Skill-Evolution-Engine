# DOCKER.md — 前端容器使用手册

> 这份文档是讲前端容器 (`review-frontend-host`)。
> 因为前端代码**修改后**需要重新 build 才能生效，本文着重讲"哪里是哪里"。
>
> 你改前端代码 → 重 build → 重起容器三步，本文都覆盖。

---

## 1. 容器现在长什么样

```
┌──────────────────────────────────────────────────────────┐
│ 容器 review-frontend-host                                │
│ 镜像 review-frontend:host                                │
│ 启动方式: docker run --name review-frontend-host ...    │
│ 自动重启: unless-stopped (主机重启会自动起来)            │
│ 网络: host 端口 5180 ↔ 容器 端口 5180                    │
│                                                          │
│ 内部基础镜像: aurora-release-docker.artnj.zte.com.cn/   │
│               arch_metric/aes/aes-measure-base:v3       │
│                                                          │
│ 内部 nginx 路径:                                         │
│   /usr/local/nginx-1.21.6/sbin/nginx  (1.21.6)          │
│   /usr/local/nginx-1.21.6/conf/nginx.conf  (默认)       │
│                                                          │
│ 我们加的文件:                                             │
│   /etc/nginx/conf.d/review.conf         (server block)   │
│   /usr/share/nginx/html/                 (静态资产)      │
│     ├── index.html                                        │
│     └── assets/                                           │
│         ├── index-XXXX.js                                  │
│         └── index-XXXX.css                                 │
└──────────────────────────────────────────────────────────┘
```

## 2. 怎么"进"容器

### 2.1 进容器 shell（看里面、看日志、改 conf）

```bash
sudo docker exec -it review-frontend-host bash
```

> 注意：`/etc/init.d/nginx` 不存在（base 镜像里 init.d 没有 nginx 启动脚本）。
> 我们靠 `CMD ["nginx", "-g", "daemon off;"]` 拉起 — 直接前台跑。

### 2.2 看 nginx 配置

容器里看：

```bash
sudo docker exec review-frontend-host cat /etc/nginx/conf.d/review.conf
```

host 上看源（**改这个才会反映**到容器）：

```bash
cat frontend/nginx.host.conf
```

> 注意：源在 `frontend/nginx.host.conf`，但**改它不会立即生效**。
> 你需要 `bash scripts/start-host.sh rebuild`，才会重 build 镜像 + 重起容器。

### 2.3 看容器日志

```bash
bash scripts/start-host.sh logs
# 等价于:
docker logs -f review-frontend-host
```

### 2.4 看 dist 内容（容器内）

```bash
sudo docker exec review-frontend-host ls /usr/share/nginx/html/assets/
```

## 3. 改前端代码 → 怎么"推上去"

完整流程：

```
1. 编辑文件:
   frontend/src/components/DiffViewer.tsx
   ... 或任何 frontend/src/**.{ts,tsx,css} 文件

2. 在 host 上 build 出 dist:
   cd frontend
   ./node_modules/.bin/vite build
   cd ..

3. 重 build 镜像 + 重起容器:
   bash scripts/start-host.sh rebuild
```

> 上面 3 步可以一次性完成：
> ```bash
> bash scripts/start-host.sh rebuild
> ```
> 它内部包含了 `vite build` + `docker build` + 重起容器。

### 3.1 改完代码**没**改 vite 配置 → 直接 `rebuild`

```bash
bash scripts/start-host.sh rebuild
```

### 3.2 改了 `vite.config.ts` 或 `frontend/Dockerfile.host` 或 `frontend/nginx.host.conf`

也得 `rebuild`（你说这 3 个文件都不会经常改，但万一改了）。`rebuild` 全自动：

- 删旧镜像
- 用新代码 build 镜像（包含新的 Dockerfile + 新的 nginx.conf + 新的 dist）
- 重起容器

### 3.3 只想"重启容器"用同一份镜像（不动 dist）

```bash
bash scripts/start-host.sh restart
```

（这个比 rebuild 快，跳过 npm build 和 docker build）

## 4. dist 是干嘛的，为什么每次 build 都产生新 hash

```bash
ls -la frontend/dist/assets/
# index-B8tJvopi.css
# index-CL9RNUxr.js      ← 这次 build 出来的 (hash 是基于内容算的)
```

hash 是内容 hash —— **改了代码，hash 就变**，浏览器就能拿到新版本。

`index.html` 里写的是相对路径 `/assets/...`：

```bash
cat frontend/dist/index.html
#  <script src="/assets/index-CL9RNUxr.js">
```

nginx 容器里这个文件位置是 `/usr/share/nginx/html/index.html`。

## 5. 公司内网访问的入口

```
http://10.90.213.38:5180/
```

同事用这个就能打开页面。改了前端代码 + rebuild 后，**他们需要 `Ctrl+Shift+R` 硬刷一次**才能拿到新版本（浏览器 cache 老的 `index.html` hash）。

## 6. 常见问题

### 6.1 同事访问空白 / 旧版本

**他们的浏览器 cache**：
让他们按 `Ctrl+Shift+R` 硬刷一次。

### 6.2 同事访问不到 5180 端口

排查：

```bash
# 1. 容器在吗?
docker ps --filter "name=review-frontend-host"

# 2. 端口监听吗?
ss -tlnp | grep 5180

# 3. host 上 curl 试一下
curl --noproxy '*' -sS -o /dev/null -w '%{http_code}\n' http://10.90.213.38:5180/api/runs

# 4. 防火墙?
sudo firewall-cmd --list-ports 2>/dev/null
sudo iptables -L -n | grep 5180

# 5. 后端 uvicorn 在吗?
bash scripts/start-backend.sh status
```

### 6.3 改前端代码，浏览器看不到变化

1. 你跑了 `rebuild` 吗？
2. 浏览器硬刷了吗？
3. 看 `frontend/dist/index.html` 里 `.js` 文件名是否变了：

```bash
grep -o 'index-[A-Za-z0-9]*\.js' frontend/dist/index.html
```

新的 hash ≠ 老 hash，说明 dist 是新的。如果 hash 没变 — **你跑 build 没成功**。

### 6.4 nginx 起来 1 秒就崩了

看容器日志：

```bash
bash scripts/start-host.sh logs
```

常见原因：

- 改坏了 `nginx.host.conf`（语法错）— 还原回去再 rebuild
- 容器里端口冲突 — 不太可能

### 6.5 想"完全清掉重来"

```bash
bash scripts/start-host.sh stop
docker rmi -f review-frontend:host
rm -rf frontend/dist
bash scripts/start-host.sh start
```

## 7. 手动 vs `bash scripts/start-host.sh` 的取舍

| 事 | 推荐用法 |
|---|---|
| 改前端代码 | `bash scripts/start-host.sh rebuild` |
| 改了 nginx.host.conf | `bash scripts/start-host.sh rebuild` |
| 只重启容器（看是不是崩了） | `bash scripts/start-host.sh restart` |
| 看容器状态 | `bash scripts/start-host.sh status` |
| 看容器日志 | `bash scripts/start-host.sh logs` |
| 容器里手动调试 | `sudo docker exec -it review-frontend-host bash` |

> **没事别直接 `docker run`** —— 绕过脚本的话端口参数 / 网络设置 / 重启策略都不会加，走脚本就不会忘。

---

## 8. 对比一下：后端跑在哪？

| 部分 | 在哪 | 控制脚本 |
|---|---|---|
| 前端 nginx | docker 容器 `review-frontend-host` | `bash scripts/start-host.sh` |
| 后端 uvicorn | 你**这台主机**上的 Python 进程 (`pid /tmp/review-backend.pid`) | `bash scripts/start-backend.sh` |
| **数据库** | 公司 MySQL `10.89.245.224:3306`（远程） | — |

后端不是容器，是个 host 进程，所以"改代码**单纯重启后端**"是：

```bash
bash scripts/start-backend.sh restart
```

**改前端**走 `rebuild`，**改后端**走 `restart` —— 两个互不干扰，可以独立发布。
