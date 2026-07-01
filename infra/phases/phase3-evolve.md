# 阶段 3 · Skill 进化（evolver agent 消费 analysis_report.json）

## 目标

消费阶段 2 输出的 `analysis_report.json`，**逐 suggestion** 生成 patch 或新 SKILL.md，让 skill 在下次执行同类需求时**不再犯同样的错**。

## 与旧版的本质区别

| 旧版 | 新版 |
|---|---|
| 强制 3 种 evolution_type（FIX/DERIVED/CAPTURED） | **不预设**——按 `target_skill` + `direction` 自然语言描述决定是 patch 还是新文件 |
| subagent 读 JSON 任务文件 + 写 SKILL_v2.md | evolver agent 直接读 `analysis_report.json` + 写 `skills/{name}/SKILL.md`（原位升级） |
| Patch 解析 shell 包装 | 用 `infra/core/patch/patch_parser.py` 纯 Python 应用 |

## 入口

```bash
PYTHONPATH=infra python infra/scripts/see-evolve.py <analysis_report.json> <skills_dir> [<evolved_skills_dir>]
```

参数：
- `<analysis_report.json>`：阶段 2 输出（必填）
- `<skills_dir>`：被进化的 skill 源目录（必填；如 `~/.claude/skills` 或 `evidence/被测项目的 skills/`）
- `<evolved_skills_dir>`：可选，进化后副本目录（默认 `<skills_dir>/../evolved_skills/`）

## evolver agent 工作循环（每条 suggestion）

1. **读 suggestion**——`id / priority / target_skill / direction / evidence_uuids / rationale`
2. **读 SKILL.md**——`skills_dir/{target_skill}/SKILL.md`
3. **决定形式**——
   - `direction` 是"在 X 段增加 Y 条款" → 输出 **Patch 格式**（原地修改）
   - `direction` 是"重写整个 skill" 或"创建新 skill" → 输出 **完整 SKILL.md**
4. **生成内容**——
   - Patch：`*** Begin Patch` / `@@ 锚点` / `-/+` / `*** End Patch`
   - 新文件：YAML frontmatter + 完整内容
5. **应用**——用 `core/patch/patch_parser.py` 解析 + 应用
6. **自评**——输出 `<EVOLUTION_COMPLETE>` 或 `<EVOLUTION_FAILED>`
7. **失败回退**——若 patch 的 `@@` 锚点找不到，自动回退到 "生成完整 SKILL_v2.md 写到 evolved_skills_dir"

## 输出格式

### Patch 格式（推荐，原位升级）

```
CHANGE_SUMMARY: <一句话描述修复内容>

*** Begin Patch
*** Update File: SKILL.md
@@ ## 错误处理
 ## 错误处理
+
+如果遇到 ImportError，先 pip install 缺失的包再重试，最多 3 次。
*** End Patch

<EVOLUTION_COMPLETE>
```

### 完整 SKILL.md（新文件 / 重写）

```
CHANGE_SUMMARY: <一句话描述>

---
name: <skill_name>
description: <新description>
---

# <Skill标题>

<完整内容>

<EVOLUTION_COMPLETE>
```

### 失败

```
<EVOLUTION_FAILED>
原因: <简要解释>
```

## `analysis_report.json` 与 evolver 的耦合点

evolver **不**重新分析数据，**只**消费 4 个字段：

```json
{
  "suggestions": [
    {
      "id": "sg-001",
      "priority": "high",
      "target_skill": "查询需求信息",
      "direction": "...",
      "evidence_uuids": ["..."],
      "rationale": "..."
    }
  ]
}
```

`failure_attribution.is_*_fault` 字段给 evolver 一个**信号**，决定改不改 SKILL.md：
- `is_skill_design_fault=true`：应改 SKILL.md
- `is_agent_misuse=true`：不一定要改 skill（可能是 prompt 问题或 transient）
- `is_environment_fault=true`：先不改 skill，加 README/部署说明

## 调用 patch_parser

```python
from core.patch.patch_parser import apply_patch_text
result = apply_patch_text(skill_path, patch_str)  # bool: 成功/失败
```

若失败，evolver 应自动回退到"输出完整 SKILL_v2.md"模式，避免阻塞流程。

## 完成条件

- 所有 `priority != "low"` 的 suggestion 都处理完毕
- 成功的 patch / 新文件**可读**（人工抽查 1-2 个）
- 至少 1 个 `<EVOLUTION_COMPLETE>`，或全部 `<EVOLUTION_FAILED>` 并给出原因

## 失败模式

| 现象 | 原因 | 解决 |
|---|---|---|
| `target_skill 不存在` | skills_dir 路径错 / 拼写错 | 检查 `<skills_dir>/{target_skill}/SKILL.md` |
| `锚点行未找到` | Patch 上下文与现版 SKILL.md 不一致 | 自动回退到"完整 SKILL_v2.md"模式 |
| `evolved_skills_dir 已存在` | 历史产物 | 加 `--overwrite` 或用时间戳目录 |

## 设计取舍

- **不写 `SKILL_v2.md`**——直接升级 `SKILL.md`（原位），evolved_skills_dir 留作历史回滚点
- **失败回退**——锚点找不到时不要硬卡，回退到"完整文件"模式更鲁棒
- **优先级**——`high > medium > low`，low 可跳过（不阻塞流程）
- **Anti-loop**——v1 不做，等 v2 加进化历史检查
- **不调外部 LLM**——evolver 由主 agent 调度时**自带 LLM 能力**，本脚本只做"应用 patch"的副作用
