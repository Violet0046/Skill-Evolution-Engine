# 阶段 2 · 失败分析（analyzer agent + 3 个 see_* 工具）

## 目标

让 LLM **自助探索 session 失败数据**，在不大面积读 session 全文的前提下，**结合"需求分析 agent"的领域知识**，输出一份结构化的 `analysis_report.json`。

## 与旧版的本质区别

| 旧版 | 新版 |
|---|---|
| Python 按 skill 维度预聚合所有 session 摘要 | **LLM 自主探索**，Python 只暴露 3 个查询工具 |
| 强制按 evolution_type（FIX/DERIVED/CAPTURED）分类 | **不预设类型**——LLM 用自然语言描述每条建议 |
| 多个 session 合并为 1 个 skill 摘要（丢 trace） | **每个 session 独立**，LLM 按需调工具查具体 trace |

## 入口

```bash
PYTHONPATH=infra python infra/scripts/see-analyze.py <session_id> [<projects_simplified_dir>]
```

参数：
- `<session_id>`：目标 session UUID（必填）
- `<projects_simplified_dir>`：可选，默认 `evidence/projects-simplified`

## 工具集

3 个 `see_*` 工具对应宏观/中观/微观三层抽象：

| 工具 | 抽象层级 | 用途 | 调用时机 |
|---|---|---|---|
| `see_failure_overview` | 宏观 | session 统计 + top 失败模式 | 入口必调，1 次 |
| `see_find_by_pattern` | 中观 | 按 `tool_name:error[:80]` 模式找 hit | 选 1-3 个高频 pattern，各 1 次 |
| `see_entry_detail` | 微观 | 单 entry 完整上下文（T1→T2→T3→T4） | 选 1-2 个 hit 看完整 trace，各 1 次 |

**不变量**：每个失败 pattern 至少要看 1 个 `entry_detail` 才能给出建议。**禁止仅凭 pattern 名瞎说**。

## analyzer agent 工作循环

1. **overview**——看 stats 和 top_patterns，识别高频模式
2. **find**——对 top 1-3 pattern 各调一次 `see_find_by_pattern`，看 hit 分布（main / subagent 占比、错误种类）
3. **detail**——对 1-2 个 hit 调 `see_entry_detail`，看 T1 reasoning_before / T2 工具调用 / T3 错误 / T4 reasoning_after
4. **归因**——结合"需求分析 agent"领域知识（CLAUDE.md 5 层架构、phase 流程、skill 列表）判断：
   - 这是 SKILL 指令的问题？（"skill_v1 应该这样做但实际没做"）
   - 这是 agent 误用工具的问题？（"skill 没规定，但 agent 应该主动……"）
   - 这是工具/环境的问题？（"MCP 报错 / 路径错"）
5. **写报告**——输出 `analysis_report.json`

## 输出：`analysis_report.json`

```json
{
  "session_id": "5527b413-...",
  "generated_at": "2026-07-01T...",
  "domain_context": "5GNR 需求分析 agent（CLAUDE.md 4 阶段：需求澄清→任务规划→需求分析→需求总结）",
  "patterns_analyzed": [
    {
      "pattern": "Bash:Exit code 1",
      "occurrences": 8,
      "main_count": 4,
      "subagent_count": 4,
      "evidence_uuids": ["dbad6dda-...", "..."]
    }
  ],
  "details_reviewed": [
    {
      "uuid": "dbad6dda-...",
      "tool_name": "Bash",
      "reasoning_before": "我需要调用 query_simple.py 查询需求信息",
      "error_output": "ImportError: No module named requests",
      "reasoning_after": "让我换一种方式..."
    }
  ],
  "failure_attribution": [
    {
      "pattern": "Bash:Exit code 1",
      "root_cause": "skill '查询需求信息' 引用了 query_simple.py 但未声明依赖 requests；该 subagent 缺 Python 包",
      "is_skill_design_fault": true,
      "is_agent_misuse": false,
      "is_environment_fault": true
    }
  ],
  "suggestions": [
    {
      "id": "sg-001",
      "priority": "high",
      "target_skill": "查询需求信息",
      "target_file": "skills/查询需求信息/SKILL.md",
      "direction": "在 SKILL.md 头部增加 '依赖环境' 段，列出需要 pip install 的包；或在 scripts/query_simple.py 顶部加 try/except + 友好报错",
      "evidence_uuids": ["dbad6dda-...", "61be7587-..."],
      "rationale": "8 次 Exit code 1 中 6 次是 ImportError，重复犯同一错误说明 skill 缺前置声明"
    }
  ],
  "notes": "本 session 共 7h / 2417 entries / 27 errors；errors 集中在 '查询需求信息' subagent 调用上，主流程仅 4 次错误"
}
```

## 调用风格

```bash
# 一次性调 macro 工具
PYTHONPATH=infra python -m core.failure_analyzer overview <sid>

# 列所有失败模式
PYTHONPATH=infra python -m core.failure_analyzer find <sid>

# 查具体 hit
PYTHONPATH=infra python -m core.failure_analyzer find <sid> "Bash:Exit code 1"

# 取单 entry 完整 trace（T1→T2→T3→T4）
PYTHONPATH=infra python -m core.failure_analyzer detail <sid> <uuid>
```

退出码恒 0，找不到返 `{"error": "..."}`（LLM 不要把"找不到"当 fatal）。

## 完成条件

- `see-analyze.py` 退出码 0
- `analysis_report.json` 存在且可被 `see-evolve.py` 解析
- `suggestions` 数组**非空**（否则说明 session 没有可进化的失败，复用旧 skill）
- 每条 suggestion 必须含 `evidence_uuids` 数组（至少 1 个），保证可追溯

## 失败模式

| 现象 | 原因 | 解决 |
|---|---|---|
| `session not found` | 路径错 / 阶段 1 未跑 | 跑 `see-collect.py` |
| `no patterns found` | session 0 错误 | 查 `overview` 确认 total_errors |
| `evidence_uuids 为空` | LLM 没看 detail | 重跑，要求至少看 N 个 detail |

## 设计取舍

- **analyzer 不读 SKILL.md**——防止先入主。归因必须基于失败证据，LLM 先看错在哪，再判断要不要改 skill
- **analyzer 不直接改任何文件**——只写报告。所有写入动作交给阶段 3 的 evolver
- **suggestion 不预设类型**——没有 FIX/DERIVED/CAPTURED 强制分类。LLM 用自然语言写 direction，由 evolver 自己判断是 patch 还是新文件
- **`is_skill_design_fault` / `is_agent_misuse` / `is_environment_fault` 三分**——给 evolver 一个明确信号，避免把"环境问题"误判为"skill 该改"
- **per-session 分析**——v1 不做跨 session 聚合，跨 session 留给 v2
