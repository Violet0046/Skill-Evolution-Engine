# review-system / backend

FastAPI 后端, 让评审员通过前端查看 `see_evolution_change` 的产物并提交决策.

## 当前状态

**开干 1 + 开干 2 完成**: 4 个核心 API 都从 MySQL 实际查/写. 列表 API 用 LEFT JOIN + GROUP BY 一次性返回评审计数. Decision 用 DB 端 `NOW(3)` 写入 reviewed_at (跨进程一致).

## 启动

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e .                # 装 FastAPI / SQLAlchemy / PyMySQL 等依赖
uvicorn app.main:app --reload --port 8000
```

## 验证 (curl)

启动后另开终端:

```bash
# 健康检查 (应返回 {"status":"ok"})
curl http://localhost:8000/healthz

# 列表 API (开干 1: 返回 [])
curl http://localhost:8000/api/runs/2026-07-25-141911/changes

# 详情 API (开干 1: 返回 404)
curl http://localhost:8000/api/changes/1

# evidence API (开干 1: 返回 404)
curl 'http://localhost:8000/api/evidences?session_id=x&uuid=y'

# 决策 API (开干 1: 返回 200 mock)
curl -X POST http://localhost:8000/api/changes/1/decisions \
     -H 'Content-Type: application/json' \
     -d '{"decision":"approved","comment":"test"}'
```

## Swagger UI

启动后浏览器打开 <http://localhost:8000/docs>, 应能看到 4 个路由分组:
- changes (GET list + GET detail)
- evidences (GET)
- decisions (POST)

## 配置

`.env` 在 `backend/`, 与 SEE 项目根的 `.env` 字段一致:

```
REVIEW_DB_HOST=10.89.245.224
REVIEW_DB_PORT=3306
REVIEW_DB_USER=knowledge_user
REVIEW_DB_PASSWORD=Qwer!234
REVIEW_DB_DATABASE=knowledge_engineering
```

`.env` 已被 `.gitignore` 排除, 不会进版本库.

## 目录结构

```
backend/
├── .env                   # 已 gitignored
├── pyproject.toml
├── README.md
├── Dockerfile             # 后续 docker-compose 用
└── app/
    ├── main.py            # FastAPI 入口 + CORS + router mount
    ├── config.py          # .env 加载 → Settings 单例
    ├── db/
    │   ├── session.py     # engine + SessionLocal + get_db context
    │   └── queries.py     # SELECT SQL 集合 (开干 2 填充)
    ├── schemas/           # Pydantic 出入参 (API 协议)
    │   ├── change.py
    │   ├── evidence.py
    │   └── decision.py
    └── api/               # FastAPI router
        ├── changes.py
        ├── evidences.py
        └── decisions.py
```

## 关联表 schema

评审后端**只读+写**这些表 (在 SEE 项目的 MySQL 库内, 不在此仓库):

| 表 | DDL 位置 | 后端用途 |
|---|---|---|
| `see_run_session` | `../infra/core/review_db/ddl/001_*.sql` | 暂未直接接 (后端只需要 run_id 列表, 跑时再动态查) |
| `see_analysis_report` | `../infra/core/review_db/ddl/002_*.sql` | 暂未直接接 |
| `see_evidence` | `../infra/core/review_db/ddl/003_*.sql` | GET /api/evidences |
| `see_evolution_change` | `../infra/core/review_db/ddl/004_*.sql` | GET /api/runs/{run_id}/changes, GET /api/changes/{id} |
| `see_review_decision` | `../infra/core/review_db/ddl/005_*.sql` | POST /api/changes/{id}/decisions |

## 不依赖 SEE 项目 Python 代码

本目录是一个**独立可运行**的 Python 项目, 不 import SEE 仓库任何 `core.*` 模块.
只通过 SQL 看到表存在.
