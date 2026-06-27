# Skill Evolution Engine

从 Claude Code session 中提取结构化证据，分析失败模式，进化 skill 定义。

## 智能体定位

- 本智能体专注于 skill 进化，通过分析 session 证据数据，识别问题并生成改进后的 skill 定义
- 目标是实现"数据采集 → 失败分析 → skill 进化"的全流程自动化

## 项目结构

```
~/.claude/agents/Skill-Evolution-Engine/
├── CLAUDE.md               # 本文件
├── infra/
│   ├── phases/             # 阶段说明
│   │   ├── phase1-collect.md
│   │   ├── phase2-analyze.md
│   │   └── phase3-evolve.md
│   ├── scripts/main/       # 主脚本
│   ├── scripts/subagent/   # subagent 脚本
│   └── core/               # 核心模块
├── rules/                  # 规则文件
└── prompts/                # 提示词模板
```

## 工作流

三个阶段，必须按顺序执行：

1. **数据采集** → 按 `infra/phases/phase1-collect.md` 执行
2. **失败分析** → 按 `infra/phases/phase2-analyze.md` 执行
3. **Skill 进化** → 按 `infra/phases/phase3-evolve.md` 执行

## 执行规则

- 执行命令时，只执行脚本，不输出额外解释
- 使用中文回答
- 默认目录为当前工作目录
