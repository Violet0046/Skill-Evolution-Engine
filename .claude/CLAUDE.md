# 已注册的工作流工具

## Skill-Evolution-Engine (技能进化引擎)

**重要：这是一个工作流（Workflow），不是 Skill。请勿使用 Skill 工具调用。**

用途：从 Claude Code session 中提取结构化证据，分析失败模式，进化 skill 定义

### 何时触发

当用户提到以下关键词时：
- "采集 session" / "提取证据" / see-collect
- "分析失败" / "失败模式" / see-analyze
- "进化 skill" / "skill 进化" / see-evolve
- "Skill-Evolution-Engine" / "SEE"

### 触发后操作

1. 读取完整工作流定义：`~/.claude/agents/Skill-Evolution-Engine/CLAUDE.md`
2. 严格按照该文件定义的工作流执行
3. 直接使用 Bash 工具执行脚本，不要调用 Skill 工具

### 执行规则

- 只执行脚本，不输出额外解释
- 不询问用户确认
- 使用中文回答
