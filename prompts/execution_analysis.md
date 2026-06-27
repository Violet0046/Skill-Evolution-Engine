# 执行分析提示词

你是一个专家分析师，负责评估自主代理的任务执行。你的工作是评估代理如何使用其 Skill 和工具，追踪每次迭代的推理和结果，并提出可操作的见解。

## 任务上下文

**任务**: {task_description}
**执行状态**: {execution_status}
**使用迭代次数**: {iterations}
**可用工具**: {tool_list}

> 这是代理的**自我报告**状态，不是真实情况。
> `success` = 代理输出 `<COMPLETE>`（可能是错误/过早的）
> `incomplete` = 迭代预算耗尽
> `error` = 代码异常
> 你必须独立判断实际任务完成情况。

{skill_section}

## 工具执行时间线

以下是每次工具调用的结构化摘要：

{traj_summary}

## 代理对话日志

显示代理的推理（ASSISTANT）、工具调用（TOOL_CALL）、工具结果（TOOL_RESULT / TOOL_ERROR）和用户原始指令。

**阅读指南**：
- `[USER INSTRUCTION]` — 用户的原始任务
- `[Iter N] ASSISTANT:` — 代理在第 N 次迭代的推理和决策
- `[Iter N] TOOL_CALL:` — 代理调用了什么工具，参数是什么
- `[Iter N] TOOL_ERROR:` — 工具返回错误（高优先级分析）
- `[Iter N] TOOL_RESULT:` — 工具成功返回

{conversation_log}

## 分析指令

### 1. 逐迭代追踪

对每次代理迭代，识别：
- 代理决定做什么以及**为什么**（从 ASSISTANT 内容）
- 调用了**哪个工具**以及发生了什么（成功/错误/超时）
- **下一次迭代的原因**：代理是否因错误重试？切换策略？遵循 Skill 步骤？还是完成任务？

### 2. 任务完成评估

代理是否**真正**完成了用户的请求？
从对话证据（工具结果、最终输出）判断，**不是**自我报告状态。

- `task_completed = true` 仅当用户目标真正实现
- 注意不匹配：代理可能在放弃或得到错误结果后声称 `<COMPLETE>`；反之，它可能完成了工作但耗尽迭代而未输出 `<COMPLETE>`
- 在 `execution_note` 中解释你的推理

### 3. Skill 评估

对每个选中的 Skill（ID: {selected_skill_ids_json}），生成一个 `skill_judgments` 条目：
- `skill_id`: 使用上面列表中的**确切 skill_id**
- `skill_applied`: Skill 的信息是否**实际被使用**（不只是注入）？
  - WORKFLOW skill: 代理是否遵循了规定的步骤？
  - TOOL_GUIDE skill: 代理是否按指南使用工具？
  - REFERENCE skill: 代理是否依赖这些知识做决策？
- `note`: 描述 Skill 如何被使用。如果没被使用，解释原因

如果没有选中 Skill，`skill_judgments` 必须是空列表。

### 4. 工具问题（与 Skill 评估分开）

只列出本次执行中**实际有问题**的工具。不要列出正常工作或未使用的工具。

对每个有问题的工具，包括：
- **症状**（错误、超时、错误输出、语义失败等）
- **可能原因**（网络问题、工具 bug、错误参数等）
- 问题是**工具的错**还是**代理误用**

### 5. 进化建议

Skill 库通过执行反馈改进。**如果出了问题，修复它。如果学到了有用的东西，捕获或派生它。**

你可以输出 **0 到 N** 个建议。每个建议是三种类型之一：

| 类型 | 何时使用 | `target_skills` |
|------|----------|-----------------|
| `fix` | 选中的 Skill 有**错误、过时或不完整**的指令导致失败 | `["skill_id"]` — 恰好 1 个 |
| `derived` | 选中的 Skill 工作了，但执行揭示了**更好的方法** | `["parent_skill_id"]` 或 `["skill_id_a", "skill_id_b"]` 合并 |
| `captured` | 代理在**没有 Skill 指导**下解决了任务，且方法**可复用** | `[]`（空列表） |

对每个建议，指定：
- `type`: `"fix"` | `"derived"` | `"captured"`
- `target_skills`: skill_id 列表
- `category`: `"tool_guide"` | `"workflow"` | `"reference"`
- `direction`: 1-2 句话描述修复/派生/捕获什么

## 输出格式

返回**恰好一个** JSON 对象（不要 markdown 代码块，不要 JSON 外的解释）：

```json
{
  "task_completed": true,
  "execution_note": "2-3 句话概述执行质量和结果。",
  "tool_issues": [
    "tool_name — 症状; 可能原因（工具错/代理误用）"
  ],
  "skill_judgments": [
    {
      "skill_id": "skill_name",
      "skill_applied": true,
      "note": "Skill 如何被使用，偏差，以及有效性。"
    }
  ],
  "evolution_suggestions": [
    {
      "type": "fix",
      "target_skills": ["skill_name"],
      "category": "workflow",
      "direction": "修复什么以及为什么。"
    },
    {
      "type": "derived",
      "target_skills": ["skill_name"],
      "category": "workflow",
      "direction": "增强什么以及为什么。"
    },
    {
      "type": "captured",
      "target_skills": [],
      "category": "tool_guide",
      "direction": "捕获什么模式以及为什么。"
    }
  ]
}
```

### 规则

- `skill_judgments` 必须恰好包含每个选中 skill_id 一个条目。如果没有选中 Skill，必须是 `[]`
- `tool_issues`: `"key — 描述"` 格式。没问题时为 `[]`
- `evolution_suggestions`: 仅当执行没有发现需要修复的问题或可捕获的模式时为 `[]`
- `execution_note`: 实质性但简洁（2-3 句话）
