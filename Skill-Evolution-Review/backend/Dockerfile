# review-system backend image
# 用于 docker-compose 一键起. 构建上下文应该是 backend/ 目录.
# 公司网络访问 docker.io 不通, 走 artxa 镜像仓库
FROM public-docker-virtual.artxa.zte.com.cn/library/python:3.11-slim

# 减小镜像体积: 不缓存 pip 与缓存的 .pyc 文件
ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# 依赖先行, 利用 docker layer cache
COPY pyproject.toml ./
COPY app ./app

# pip install . (依赖来自 pyproject.toml)
RUN pip install .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
