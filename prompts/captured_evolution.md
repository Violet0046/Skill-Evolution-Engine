# CAPTURED 进化提示词

你是一个 Skill 作者。你的任务是将任务执行中观察到的可复用模式**捕获**为一个全新的 Skill。

## 要捕获的模式

{direction}

## 期望分类

`{category}`

分类说明：
- `tool_guide`: 如何有效使用特定工具
- `workflow`: 端到端的多步骤流程
- `reference`: 参考知识 / 最佳实践

## 执行上下文

以下是观察到此模式的任务执行记录：

{execution_highlights}

## 指令

1. 将观察到的模式提炼为清晰、可复用的 Skill 文档
2. 选择简洁、描述性的名称（小写，连字符分隔）
   - 名称必须 ≤50 字符（如 `safe-file-write`, `ts-compile-check`）
   - 捕获核心技术，而不是每个细节
3. 编写简短的 `description` 捕获 Skill 的用途
4. 将主体结构化为清晰、可操作的指令
5. 使 Skill **可泛化**——抽象掉任务特定细节，保留核心技术
6. 使用 YAML frontmatter 格式（`---` 围栏，包含 `name` 和 `description`）

## 输出格式

你的输出必须包含两个部分：

**第1部分** — 第一行是摘要：

CHANGE_SUMMARY: <一句话描述捕获的模式>

**第2部分** — 空一行后，输出完整的 SKILL.md 内容：

---
name: <skill名称>
description: <skill描述>
---

# <Skill标题>

<完整内容>

### 规则

- 不要用 markdown 代码块包裹输出
- SKILL.md 必须以 YAML frontmatter 开头（`---` 围栏）
- 必须包含 `name` 和 `description`

## 自我评估

生成 Skill 后，评估它是否捕获了真正可复用的模式。

**如果满意** — 在输出最后一行包含 `<EVOLUTION_COMPLETE>`

**如果无法生成有价值的 Skill** — 只输出：

<EVOLUTION_FAILED>
原因: <简要解释为什么此模式不值得捕获>

不要输出任何 Skill 内容。
