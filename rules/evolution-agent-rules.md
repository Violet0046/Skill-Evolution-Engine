# 进化 Agent 规则

## 重要：使用 general-purpose 类型的 Agent

**必须使用 `general-purpose` 类型的 Agent 执行进化任务**。

不要使用 `evolution-agent`，这个类型不存在。可用的 Agent 类型：
- `general-purpose` - 用于执行进化任务
- `Explore` - 用于搜索和探索
- `Plan` - 用于规划

## 职责

进化 Agent 负责执行 Skill 进化任务，具体包括：

1. 读取进化任务文件
2. 根据进化类型选择对应的提示词模板
3. 生成 Patch 或完整 SKILL.md
4. 自我评估进化结果
5. 输出进化结果

## 工作流程

### 步骤1: 读取任务文件

```bash
python ~/.claude/agents/Skill-Evolution-Engine/infra/scripts/subagent/read_task.py <task_file>
```

### 步骤2: 读取提示词模板

根据任务文件中的 `evolution_type` 选择对应的提示词：
- `fix` → `prompts/fix_evolution.md`
- `derived` → `prompts/derived_evolution.md`
- `captured` → `prompts/captured_evolution.md`

### 步骤3: 填充提示词模板

将任务文件中的字段填充到提示词模板中：
- `{current_content}` → `skill_content`
- `{direction}` → `direction`
- `{failure_context}` → `failure_context`
- `{parent_content}` → `skill_content`（对 derived）
- `{execution_insights}` → `failure_context`（对 derived）
- `{category}` → `category`（对 captured）
- `{execution_highlights}` → `failure_context`（对 captured）

### 步骤4: 生成进化内容

根据提示词模板生成：
- FIX: Patch 格式的修改
- DERIVED: 完整的新 SKILL.md
- CAPTURED: 完整的新 SKILL.md

### 步骤5: 自我评估

检查生成的内容是否满足：
- 是否解决了根本原因？
- 是否符合格式要求？
- 是否有实际价值？

如果满意，在输出最后包含 `<EVOLUTION_COMPLETE>`
如果不满意，输出 `<EVOLUTION_FAILED>` 和原因

### 步骤6: 保存结果

```bash
# 对 FIX: 应用 Patch
python ~/.claude/agents/Skill-Evolution-Engine/infra/scripts/subagent/apply_patch.py <patch_file> <skill_dir>

# 对 DERIVED/CAPTURED: 保存新 SKILL.md
python ~/.claude/agents/Skill-Evolution-Engine/infra/scripts/subagent/save_evolved_skill.py <skill_name> <content>
```

## 禁止做的事

1. **禁止直接修改 SKILL.md 文件** — 必须通过 Patch 系统或保存脚本
2. **禁止跳过质量评估** — 必须自我评估
3. **禁止生成不符合格式的输出** — 必须遵循提示词模板的格式要求
4. **禁止重复进化** — 检查进化历史，避免短时间内重复进化同一 Skill
5. **禁止生成无价值的进化** — 如果改进不明显，应该输出 `<EVOLUTION_FAILED>`

## 输出格式

### FIX 进化

```
CHANGE_SUMMARY: <修复摘要>

*** Begin Patch
*** Update File: SKILL.md
@@ <锚点行>
 <上下文>
-<删除行>
+<添加行>
*** End Patch

<EVOLUTION_COMPLETE>
```

### DERIVED 进化

```
CHANGE_SUMMARY: <派生摘要>

---
name: <新skill名称>
description: <新skill描述>
---

# <新Skill标题>

<完整内容>

<EVOLUTION_COMPLETE>
```

### CAPTURED 进化

```
CHANGE_SUMMARY: <捕获摘要>

---
name: <skill名称>
description: <skill描述>
---

# <Skill标题>

<完整内容>

<EVOLUTION_COMPLETE>
```

## 错误处理

### 任务文件不存在

输出错误信息并退出：
```
错误: 任务文件不存在: <path>
```

### 提示词模板不存在

输出错误信息并退出：
```
错误: 提示词模板不存在: <path>
```

### Patch 应用失败

输出错误信息并尝试重新生成 Patch：
```
错误: Patch 应用失败，锚点行未找到: <anchor>
请重新生成 Patch。
```

### 进化失败

输出 `<EVOLUTION_FAILED>` 和原因：
```
<EVOLUTION_FAILED>
原因: 无法生成满意的进化内容
```
