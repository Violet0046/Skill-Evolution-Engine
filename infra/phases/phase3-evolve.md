# 阶段3：Skill 进化

## 目标

基于分析结果生成进化后的 SKILL。

## 步骤0：检查可进化的skill（必须先执行）

在执行进化前，必须先检查哪些skill可以进化（在skills目录中有定义）：

```bash
bash ~/.claude/agents/Skill-Evolution-Engine/infra/get_evolvable_skills.sh <output_dir> [skills_dir]
```

### 参数说明

- `<output_dir>`: 阶段1的输出目录
- `[skills_dir]`: 可选，skills 目录路径（**默认：当前工作目录下的 skills 文件夹**）

### 重要：skills 目录位置

**skills 目录默认在当前工作目录下**，不是在 agent 目录下！

- 正确：`/home/10358563/Code/测试目录/skills/`
- 错误：`~/.claude/agents/Skill-Evolution-Engine/skills/`

如果没有指定 skills_dir，脚本会自动使用当前工作目录下的 `skills/` 文件夹。

### 输出

- 列出所有可进化的skill（在skills目录中有SKILL.md文件）

### 完成条件

至少有一个skill可以进化。

## 步骤1：生成进化任务

对每个可进化的skill执行：

```bash
bash ~/.claude/agents/Skill-Evolution-Engine/infra/evolve.sh <output_dir> <skill_name> [skills_dir] [evolved_skills_dir]
```

### 参数说明

- `<output_dir>`: 阶段1的输出目录
- `<skill_name>`: 要进化的 skill 名称
- `[skills_dir]`: 可选，skills 目录路径（默认：当前目录下的 skills）
- `[evolved_skills_dir]`: 可选，进化后的 skills 输出目录（默认：当前目录下的 evolved_skills）

### 输出

- `evolved_skills/{skill_name}.json` - 进化任务文件

### 完成条件

生成进化任务文件。

## 步骤2：执行进化（subagent）

### 重要：使用 general-purpose 类型的 subagent

**不要使用 `evolution-agent` 类型**，这个类型不存在。必须使用 `general-purpose` 类型的 Agent。

### 流程

1. 读取进化任务文件（`evolved_skills/{skill_name}.json`）
2. 根据 `evolution_type` 选择对应的提示词模板：
   - `fix` → `prompts/fix_evolution.md`
   - `derived` → `prompts/derived_evolution.md`
   - `captured` → `prompts/captured_evolution.md`
3. 按照提示词模板生成 Patch 或完整 SKILL.md
4. 自我评估进化结果（输出 `<EVOLUTION_COMPLETE>` 或 `<EVOLUTION_FAILED>`）

### 进化类型

| 类型 | 触发条件 | 输出 |
|------|----------|------|
| FIX | Skill 指令有误、过时或不完整 | Patch 格式 |
| DERIVED | 执行中发现更优方案 | 完整 SKILL.md |
| CAPTURED | 无 Skill 指导下发现可复用模式 | 完整 SKILL.md |

### 输出格式

#### FIX 进化

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

#### DERIVED/CAPTURED 进化

```
CHANGE_SUMMARY: <进化摘要>

---
name: <skill名称>
description: <skill描述>
---

# <Skill标题>

<完整内容>

<EVOLUTION_COMPLETE>
```

## 步骤3：应用进化结果

### FIX 进化：应用 Patch

```bash
python ~/.claude/agents/Skill-Evolution-Engine/infra/scripts/subagent/apply_patch.py <patch_file> <skill_dir>
```

### DERIVED/CAPTURED 进化：保存新 SKILL.md

```bash
echo "<进化内容>" | python ~/.claude/agents/Skill-Evolution-Engine/infra/scripts/subagent/save_evolved_skill.py <skill_name> -
```

### 保存到 evolved_skills 目录

进化后的 skill 保存到 `evolved_skills/` 目录，方便查看效果：

```bash
# 创建 evolved_skills 目录
mkdir -p evolved_skills/<skill_name>

# 保存进化后的 SKILL.md
echo "<进化内容>" > evolved_skills/<skill_name>/SKILL.md
```

## 完成条件

- FIX 进化：Patch 成功应用（脚本退出码为 0）
- DERIVED/CAPTURED 进化：新 SKILL.md 成功保存到 evolved_skills 目录

## 常见错误

| 错误 | 原因 | 解决方案 |
|------|------|----------|
| 进化任务文件不存在 | 步骤1未执行 | 先执行 evolve.sh |
| Patch 应用失败 | 锚点行未找到 | 检查 Patch 格式 |
| `<EVOLUTION_FAILED>` | LLM 无法生成满意的进化 | 检查失败上下文 |
| Agent type 'evolution-agent' not found | 使用了错误的 Agent 类型 | 使用 `general-purpose` 类型 |
