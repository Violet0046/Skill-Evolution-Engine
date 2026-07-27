# frontend/Dockerfile — 多阶段 build
# stage1: node:20 装依赖 + tsc + vite build 出 dist/
# stage2: nginx:alpine serve dist/, 同时把 /api/* 反代到 backend
#
# 设计:
#   - 不再 npm run dev (开发模式, 太重, 每次访问都得 Vite 重新打包)
#   - 镜像出来后体积小 (~nginx + dist/), 同事启动 < 1s
#   - nginx.conf 通过 COPY 带入, 同一镜像可直接调路由
#
# build: docker build -t review-frontend:<tag> .
# 可传 build arg: VITE_API_BASE_URL (默认 /api)

# ---- stage 1: build ----
# 公司网络访问 docker.io 不通, 走 artxa 镜像仓库
FROM public-docker-virtual.artxa.zte.com.cn/library/node:20-alpine AS builder

WORKDIR /app

# 依赖先行 (利用 layer cache)
COPY package*.json ./
RUN npm ci --no-audit --no-fund || npm install --no-audit --no-fund

# 复制源码
COPY tsconfig.json tsconfig.node.json vite.config.ts ./
COPY index.html ./
COPY src ./src
COPY public ./public

# API base url: 通过 build arg 注入. 默认 /api, 由 nginx 在同镜像内反代到 backend 容器.
ARG VITE_API_BASE_URL=/api
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

RUN npm run build

# ---- stage 2: serve ----
FROM public-docker-virtual.artxa.zte.com.cn/library/nginx:1.27-alpine

# 容器内 nginx 配置: serve 静态 + /api/* -> backend:8000
COPY nginx.conf /etc/nginx/conf.d/default.conf

# 复制构建产物
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

# nginx:alpine 默认 CMD ["nginx", "-g", "daemon off;"] 已经合适
