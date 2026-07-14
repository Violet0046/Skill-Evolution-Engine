# Skill Evolution Engine

从 Claude Code session 中提取结构化证据，分析失败模式，进化 skill 定义。

## 智能体定位

- 本智能体专注于 skill 进化，通过分析 session 证据数据，识别问题并生成改进后的 skill 定义
- 目标是实现"数据采集 → 失败分析 → skill 进化"的全流程自动化

## 项目结构

```
Skill-Evolution-Engine/
├── CLAUDE.md                       # 本文件
├── infra/
│   ├── phases/                     # 3 阶段说明
│   │   ├── phase1-collect.md
│   │   ├── phase2-analyze.md
│   │   └── phase3-evolve.md
│   ├── scripts/                    # CLI 入口
│   │   ├── see-collect.py
│   │   ├── see-analyze.py
│   │   ├── see-evolve.py           # 阶段 3：单 target_file → 4 字段 JSON
│   │   ├── evolve-discovery.py     # 阶段 3：discovery，列出所有 target_file
│   │   └── with-python.sh          # Python 3.8+ 探测垫片（自动 export PYTHONPATH=infra）
│   ├── core/                       # 核心模块
│   │   ├── simplify/               # entry 字段精简
│   │   ├── failure_analyzer/       # 3 个 see_* 工具（overview/find/detail）
│   │   ├── util/                   # 通用工具（agent_meta / resolve_architecture / session_io / timestamp）
│   │   └── evolver/                # suggestions 聚合（aggregate）+ evolver prompt 组装（prompt_builder）
├── rules/                          # 3 个 agent 规则
│   ├── main-agent-rules.md
│   ├── analyzer-agent-rules.md
│   └── evolver-agent-rules.md
├── prompts/                        # 2 个 sub-agent 提示词
│   ├── analyzer-prompt.md
│   └── evolver-prompt.md
├── agent-architectures/            # 各 agent 项目架构清单（JSON，sub-agent 必读）
│   └── <agent_name>.json
└── evidence/                       # 数据目录
    ├── projects/                   # 原始 session
    ├── projects-simplified/        # 简化版（阶段 1 产出）
    ├── analysis_reports/           # analyzer 输出（<session_id>.analysis_report.json，阶段 2 产出）
    └── evolution_changes/          # evolver 输出（<flatten_target_file>.change，阶段 3 产出）
```

## 执行规则

- **必读 [`rules/main-agent-rules.md`](rules/main-agent-rules.md)**
- 执行命令时，只执行脚本，不输出额外解释
- 使用中文回答
- 默认目录为当前工作目录
- **Python 脚本必须走 `bash infra/scripts/with-python.sh` 垫片**（项目要求 Python 3.8+）。**禁止**直接 `python infra/scripts/*.py`
