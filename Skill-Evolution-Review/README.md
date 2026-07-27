# Review System

评审系统: 让评审员在浏览器查看 SEE 流水线产出的 changes, 在前端做 diff, 下钻证据,
提交评审决策.

## 架构

```
Skill-Evolution-Engine (SEE)                  Skill-Evolution-Review (本仓库)
  流水线 (Python)                                 后端 (FastAPI) + 前端 (React + shadcn/ui)
       |                                                  |
       | 写入                                            | 读 / 写
       v                                                  v
  +-----------------------------------------------------------+
  | MySQL knowledge_engineering                                |
  |   see_run_session / see_analysis_report                    |
  |   see_evidence      <--双向共享-->                         |
  |   see_evolution_change / see_review_decision               |
  +-----------------------------------------------------------+
```

**两仓库通过 MySQL schema 解耦**, 互不引用代码. 本仓库独立 git, 独立部署.

## 当前状态

| 部分 | 状态 |
|---|---|
| 后端项目骨架 (FastAPI + SQLAlchemy + PyMySQL) | ✅ 开干 1 |
| 4 个核心 API 路由 | ✅ 开干 1 |
| Settings / 数据库连接池 / Pydantic 模型 / CORS / Dockerfile | ✅ 开干 1 |
| **4 API 接真 SQL + 列表评审计数** | ✅ 开干 2 |
| **Decision reviewed_at 来自 DB NOW(3)** | ✅ 开干 2 |
| **GET /api/runs (列所有 run_id)** | ✅ 开干 3 |
| 前端 React + Vite + TypeScript | ✅ 开干 3 |
| shadcn/ui 8 个必备组件 (inline) | ✅ 开干 3 |
| 主表 + 抽屉 + 评审表单 交互 | ✅ 开干 3 |
| reviewer 必填 + 抽屉按钮联动 | ✅ 开干 3 |
| **docker-compose.yml 一键起** | ✅ 开干 3 |

## 启动方式

### 启动方式 1: 手动分两终端 (开发期推荐)

```bash
# terminal 1: 后端
cd backend
source .venv/bin/activate    # 或 venv\Scripts\activate on Windows
uvicorn app.main:app --reload --port 8000

# terminal 2: 前端
cd frontend
npm install
npm run dev                  # 启动 5173
```

浏览器打开 <http://localhost:5173>.

### 启动方式 2: Docker Compose 一键起

```bash
docker-compose up --build
```

打开 <http://localhost:5173>.

## 目录结构

```
Skill-Evolution-Review/
├── README.md                       # 本文件
├── docker-compose.yml              # 一键起 backend + frontend
├── .gitignore                      # 排除 .env, __pycache__, node_modules
├── backend/                        # FastAPI + SQLAlchemy + PyMySQL (开干 1+2)
└── frontend/                       # React + Vite + TypeScript + shadcn/ui (开干 3)
    ├── package.json
    ├── tsconfig.json
    ├── vite.config.ts
    ├── tailwind.config.ts
    ├── postcss.config.js
    ├── components.json             # shadcn 配
    ├── Dockerfile
    └── src/
        ├── App.tsx
        ├── main.tsx
        ├── index.css                # Tailwind base + shadcn vars
        ├── lib/
        │   ├── api.ts               # 5 endpoint + 类型
        │   └── utils.ts
        ├── hooks/
        │   └── useReviewer.ts       # 顶部必填 reviewer (localStorage)
        ├── components/
        │   ├── ui/                  # shadcn 8 个组件
        │   ├── ReviewerInput.tsx
        │   ├── ChangeTable.tsx     # 主表
        │   ├── ChangeDrawer.tsx     # 详情抽屉
        │   └── DecisionForm.tsx     # approve/modify/reject + 备注
        └── pages/
            └── ReviewHome.tsx       # 主页编排
```

## 验证用例 (手动)

启动后, 浏览器 <http://localhost:5173>:

1. 顶部 reviewer 输入框空时, 主表里有 12 行 (你测试用的 run)
2. 不填 reviewer 直接点列表某行 → 抽屉打开, 3 个决策按钮全 disabled, 提示 "请先填 reviewer"
3. 填 "zhouyike" 再点 → 抽屉按钮 enabled
4. 抽屉顶部: subject_target + run_id + change id
5. 抽屉中部: "Diff" 区, 2 栏 (左 ORIGINAL 右 NEW) 显示 .change 内容
6. 抽屉底部: "Suggestions" 列出每条 sg + 证据 uuid
7. 点击证据 uuid → 抓 evidence detail (5 字段), 即 detail_json
8. 点 [通过] → 关抽屉, 列表该 change 的 decision_count_approved +1
9. 点 [修改] → 输入 modified_content 后才允许提交
10. 点 [拒绝] → 列表 decision_count_rejected +1

后端 DB 验证:

```bash
mysql -h ... -u ... -p see_review -e "SELECT * FROM see_review_decision LIMIT 10;"
```

应能看到刚才评审插入的行, `reviewed_at` 是 DB 端 `NOW(3)` 写入的时间.

## 已知约束 / 后续

| 已知坑 | 状态 | 后续 |
|---|---|---|
| evidence fetch 缺 session_id (frontend 当前用 change.run_id 兜底, 没真正匹配) | MVP 可用, 但精确性不足 | **开干 4 起**: 让 ChangeOut 也带 `evidence_by_session` 聚合, 或后端加 GET /api/evidences/search?uuid=X |
| reviewer 输入没校验特殊字符, 建议先做 trim + maxLength 64 | 简单 | 后续 |
| 评审提交后没乐观更新, 等 server 200 才刷新列表 | 当前是闭抽屉后再 GET 一次 | 后续可加 React Query |
| 没跑测试 | 不在开干 3 范围 | 后续 |
