# Skill Evolution Engine

从 Claude Code session 提取结构化证据，分析失败模式，进化 skill 定义。

## 项目结构

```
Skill-Evolution-Engine/
├── .claude/                  # Claude Code 平台配置
│   ├── commands/              # slash command 入口
│   │   ├── see-collect.md
│   │   ├── see-analyze.md
│   │   └── see-evolve.md
│   └── settings.json
│
├── infra/                    # 核心代码
│   ├── phases/               # 3 阶段说明（主 agent 必读）
│   │   ├── phase1-collect.md
│   │   ├── phase2-analyze.md
│   │   └── phase3-evolve.md
│   │
│   ├── scripts/              # CLI 入口
│   │   ├── see-collect.py    # 阶段 1 → simplify
│   │   ├── see-analyze.py    # 阶段 2 → 拼 prompt → sub-agent
│   │   ├── see-evolve.py     # 阶段 3 → sub-agent
│   │   └── with-python.sh    # Python 3.8+ 探测垫片
│   │
│   └── core/                 # 核心模块
│       ├── simplify/          # 阶段 1 逻辑
│       ├── failure_analyzer/  # 阶段 2 CLI 工具
│       │   ├── overview       # 预热 .index/ 索引
│       │   ├── find          # 按 agent_type 查 hits（容错匹配）
│       │   ├── detail        # 查单条 entry
│       │   └── list
│       ├── util/              # 通用工具（含 resolve_architecture）
│       └── patch/             # Patch 解析
│
├── rules/                    # 3 个 agent 规则（主 agent 必读）
│   ├── main-agent-rules.md   # 调度层
│   ├── analyzer-agent-rules.md
│   └── evolver-agent-rules.md
│
├── prompts/                  # 2 个 sub-agent 提示词模板
│   ├── analyzer-prompt.md    # 含 {{RULES}} {{AGENT_ARCH}} 等占位符
│   └── evolver-prompt.md
│
├── agent-architectures/      # 各 agent 项目架构清单（JSON，{{AGENT_ARCH}} 内容源）
│   └── <agent_name>.json
│
└── evidence/                 # 数据目录
    ├── projects/             # 原始 session
    ├── projects-simplified/  # 简化版 session（阶段 1 产出）
    └── analysis_reports/     # analysis_report.json（阶段 2 产出）
```

## 数据流（3 阶段）

```
阶段 1                阶段 2                       阶段 3
─────────        ──────────────────         ──────────────
原始 session     简化版 session + arch JSON    analysis_report.json
   │            │                              │
   ▼            ▼                              ▼
see-collect.py  see-analyze.py                see-evolve.py
   │            │  ┌─ overview（预热 .index/） │  ┌─ resolve_arch
   │            │  ├─ resolve_arch               │  └─ sub-agent
   │            │  ├─ 读 prompts/ + rules/      │
   │            │  ├─ 替换 5 个占位符           │
   │            │  └─ 调 sub-agent                │
   ▼            ▼                              ▼
简化版 session   analysis_report.json         evolution_report.json
                 └─ Agent(type="general-purpose",
                    tools=["Bash","Write"])
```

## 关键设计点

| 关注点 | 状态 |
|---|---|
| **主 agent 调度** | `rules/main-agent-rules.md`（必读）|
| **阶段判断** | 自然语言触发 → 看 `projects-simplified/<sid>.jsonl` 标志 |
| **Sub-agent 工具集** | `tools=["Bash", "Write"]`（**不**含 Read） |
| **`see-analyze.py` 职责** | **只** 拼完整 sub-agent prompt，**不**调 sub-agent（主 agent 拿到 stdout 后**自**调） |
| **FIND 容错** | 3 层 fallback（精确 / 标准化 / 子串） |
| **Bash 兼容性** | `with-python.sh` 垫片**自动** export `PYTHONPATH=infra` |
