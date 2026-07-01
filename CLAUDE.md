# Skill Evolution Engine

从 Claude Code session 中提取结构化证据，分析失败模式，进化 skill 定义。

## 智能体定位

- 本智能体专注于 skill 进化，通过分析 session 证据数据，识别问题并生成改进后的 skill 定义
- 目标是实现"数据采集 → 失败分析 → skill 进化"的全流程自动化
- 核心创新：**不在 Python 阶段给 tool_call 贴 skill 标签**（栈式归因已废），把归因交给 LLM 结合 reasoning 自助判断

## 项目结构

```
Skill-Evolution-Engine/
├── CLAUDE.md                       # 本文件
├── infra/
│   ├── phases/                     # 3 阶段说明
│   │   ├── phase1-collect.md
│   │   ├── phase2-analyze.md
│   │   └── phase3-evolve.md
│   ├── scripts/                    # 3 个 CLI 入口
│   │   ├── see-collect.py
│   │   ├── see-analyze.py
│   │   └── see-evolve.py
│   ├── core/                       # 核心模块
│   │   ├── simplify/               # entry 字段精简（classifier + simplifier + config）
│   │   ├── failure_analyzer/       # 3 个 see_* 工具（overview/find/detail）
│   │   ├── util/                   # session_io / agent_meta / timestamp
│   │   └── patch/                  # OpenSpace Patch 解析与应用
│   └── rules/                      # 旧版预留位置（已迁到根 rules/）
├── rules/                          # 3 个 agent 规则
│   ├── main-agent-rules.md         # 调度层规则
│   ├── analyzer-agent-rules.md     # 失败分析层规则
│   └── evolver-agent-rules.md      # 进化层规则
├── prompts/                        # 2 个 sub-agent 提示词
│   ├── analyzer-prompt.md
│   └── evolver-prompt.md
└── evidence/                        # 数据目录（session 证据）
    ├── projects/                   # 原始 session
    └── projects-simplified/        # 简化版 + 失败索引（懒构建）
```

## 工作流

三个阶段，必须按顺序执行：

1. **数据采集** → 按 `infra/phases/phase1-collect.md` 执行 → 跑 `infra/scripts/see-collect.py`
2. **失败分析** → 按 `infra/phases/phase2-analyze.md` 执行 → 跑 `infra/scripts/see-analyze.py`，调度 analyzer sub-agent
3. **Skill 进化** → 按 `infra/phases/phase3-evolve.md` 执行 → 跑 `infra/scripts/see-evolve.py`，调度 evolver sub-agent

## 3 agent 协作模型

```
主 agent（read-only 编排）
├── 阶段 1：自己跑 see-collect
├── 阶段 2：调度 analyzer sub-agent（带 3 个 see_* 工具）
└── 阶段 3：调度 evolver sub-agent（带 Read/Write/Edit/Bash）
```

主 agent 规则：`rules/main-agent-rules.md`
analyzer 规则：`rules/analyzer-agent-rules.md`
evolver 规则：`rules/evolver-agent-rules.md`

## 执行规则

- 执行命令时，只执行脚本，不输出额外解释
- 使用中文回答
- 默认目录为当前工作目录
- 主 agent 不直接读 session / 不写 SKILL.md（让 sub-agent 做）
