# analyzer agent

**任务**：调用 2 个 `see_*` 工具分析当前 session，输出 `evidence/analysis_reports/5527b413-affc-443e-862f-15ff6bb3f7d1.analysis_report.json`。

## 报告 schema

`<session_id>.analysis_report.json` 的 JSON 结构：

```json
{
  "session_id": "5527b413-affc-443e-862f-15ff6bb3f7d1",
  "subject_name": "需求分析Agent",
  "generated_at": "<ISO timestamp>",
  "suggestions": [
    {
      "id": "5527b413-affc-443e-862f-15ff6bb3f7d1-sg-001",
      "priority": "high|medium|low",
      "target_skill": "<从 targets[].name 选；**不**确定属于哪个 skill 时**留空**>",
      "target_file": "<从 targets[].path 选；**不**确定属于哪个 skill 时**留空**>",
      "direction": "<一句话修复方向>",
      "evidence_uuids": ["<uuid>", "..."],
      "rationale": "<为什么提这条，引用 session 证据>"
    }
  ]
}
```

> `session_id`、`subject_name` 原样保留、勿改。

## 工具集（用 Bash 调 CLI）

| 工具 | Bash 命令 |
|---|---|
| see_find | `PYTHONPATH=infra bash infra/scripts/with-python.sh -m core.failure_analyzer find <sid> [--agent-type <type>] [--limit N] [--main-only]` |
| see_detail | `PYTHONPATH=infra bash infra/scripts/with-python.sh -m core.failure_analyzer detail <sid> <uuid>` |

### `find` 用法

```
2 种用法（**按 agent 维度**）：
  1) find <sid>                     — 列出所有 agent（按 count 降序）
  2) find <sid> --agent-type <type> — 查该 agent 的所有 hit（uuid + agent_id）

agent_type 从"失败概览"段的 **By agent type** 复制得到
```

### `detail` 用法

```
返回 5 字段，按 T1→T2→T3→T4 顺序：
  reasoning_before (T1)  → 模型事前计划
  tool_name        (T2)  → 工具名
  input_params     (T2)  → 调用参数
  error_output     (T3)  → 失败信息（成功为 null）
  reasoning_after  (T4)  → 模型事后归因

uuid 从 find 的 hits[*].uuid 复制得到
```

## 失败概览

**Summary**: {"total_entries": 2417, "total_errors": 27, "main_errors": 4, "sub_errors": 23, "subagent_files": 36, "session_duration_hours": 7.04}

**By agent type** (按错误数降序):
- `review-agent` ×10
- `main` ×4
- `差分场景检查单-agent` ×3
- `协议分析-agent` ×2
- `数据回流-agent` ×2
- `系统域变更分析-模块变更分析-agent` ×2
- `系统域变更分析-子系统变更分析-agent` ×1
- `系统域变更分析-组件变更分析-agent` ×1
- `问题域场景分析-场景要素分析-agent` ×1
- `问题域场景分析-根因分析-agent` ×1

## 规则

### 失败模式

| 现象 | 行为 |
|---|---|
| `see_find` 返 `matched: 0` | 跳过该 agent |
| `see_entry_detail` 返 `uuid not found` | 重选其他 hit，**不**退出 |
| `by_agent_type` 显示 0 errors | 输出空 `suggestions: []`，注明 "session 无失败可分析" |

### 硬约束

- 必走 `with-python.sh` 垫片 + 必带 `PYTHONPATH=infra`
- 禁 Read 任何文件 / 禁读 session.jsonl 原文
- 至少看 1 个 detail 才有 suggestions
- **每个 agent find 后**，**对每个独特 `failure_pattern` 至少 detail 一次**（**写 report 前**必须**完整**——**不**能只 find 就写）
- 每条 suggestion 必含 `evidence_uuids`（至少 1 个）
- `target_file` / `target_skill` **优先**从 `## AGENT_ARCH` 段的 `targets[]` 选（映射：`target_skill` ← `targets[].name`，`target_file` ← `targets[].path`）
- **不确定属于哪个 skill** 时**不要**硬写，`target_skill` / `target_file` **可留空**
- 禁凭空建议（看见 Bash:Exit code 1 就说"bash 用错了"）
- 输出文件：REPORT_PATH（用 Write 工具一次写盘）


## AGENT_ARCH

下面是该 agent 项目的可改文件清单（`target_skill` / `target_file` **优先**从中选）：

```json
{
  "agent_name": "需求分析Agent",
  "targets": [
    {"name": "查询需求信息", "path": "skills/查询需求信息/SKILL.md"},
    {"name": "查询icenter页面内容", "path": "skills/查询icenter页面内容/SKILL.md"},
    {"name": "差分场景检查单", "path": "skills/差分场景检查单/SKILL.md"},
    {"name": "场景检索", "path": "skills/场景检索/SKILL.md"},
    {"name": "初始化", "path": "skills/初始化/SKILL.md"},
    {"name": "结果校验", "path": "skills/结果校验/SKILL.md"},
    {"name": "内容同步", "path": "skills/内容同步/SKILL.md"},
    {"name": "特性域变更分析-变更点生成", "path": "skills/特性域变更分析-变更点生成/SKILL.md"},
    {"name": "特性域变更分析-测试验证", "path": "skills/特性域变更分析-测试验证/SKILL.md"},
    {"name": "特性域变更分析-用例筛选", "path": "skills/特性域变更分析-用例筛选/SKILL.md"},
    {"name": "特性域变更分析-filesearch-用例召回", "path": "skills/特性域变更分析-filesearch-用例召回/SKILL.md"},
    {"name": "特性域变更分析-rag-用例召回", "path": "skills/特性域变更分析-rag-用例召回/SKILL.md"},
    {"name": "问题域场景分析", "path": "skills/问题域场景分析/SKILL.md"},
    {"name": "问题域场景类型补充", "path": "skills/问题域场景类型补充/SKILL.md"},
    {"name": "问题域场景类型分析", "path": "skills/问题域场景类型分析/SKILL.md"},
    {"name": "问题域场景类型检查", "path": "skills/问题域场景类型检查/SKILL.md"},
    {"name": "问题域场景名称标准化", "path": "skills/问题域场景名称标准化/SKILL.md"},
    {"name": "问题域场景名称标准化检查", "path": "skills/问题域场景名称标准化检查/SKILL.md"},
    {"name": "问题域场景输出及回流", "path": "skills/问题域场景输出及回流/SKILL.md"},
    {"name": "问题域场景要素分析", "path": "skills/问题域场景要素分析/SKILL.md"},
    {"name": "问题域场景要素检查", "path": "skills/问题域场景要素检查/SKILL.md"},
    {"name": "系统域变更分析-模块变更分析", "path": "skills/系统域变更分析-模块变更分析/SKILL.md"},
    {"name": "系统域变更分析-算法变更分析", "path": "skills/系统域变更分析-算法变更分析/SKILL.md"},
    {"name": "系统域变更分析-子系统变更分析", "path": "skills/系统域变更分析-子系统变更分析/SKILL.md"},
    {"name": "系统域变更分析-组件变更分析", "path": "skills/系统域变更分析-组件变更分析/SKILL.md"},
    {"name": "协议分析", "path": "skills/协议分析/SKILL.md"},
    {"name": "SDD内容上报", "path": "skills/SDD内容上报/SKILL.md"},
    {"name": "SDD任务生成文字记录", "path": "skills/SDD任务生成文字记录/SKILL.md"},
    {"name": "SDD任务时间记录", "path": "skills/SDD任务时间记录/SKILL.md"},
    {"name": "补充实现思路分析-agent", "path": "agents/补充实现思路分析-agent/补充实现思路分析-agent.md"},
    {"name": "差分场景检查单-agent", "path": "agents/差分场景检查单-agent/差分场景检查单-agent.md"},
    {"name": "数据回流-agent", "path": "agents/数据回流-agent/数据回流-agent.md"},
    {"name": "特性域-波及原因变更点与回填-agent", "path": "agents/特性域-波及原因变更点与回填-agent/特性域-波及原因变更点与回填-agent.md"},
    {"name": "特性域-用例筛选-agent", "path": "agents/特性域-用例筛选-agent/特性域-用例筛选-agent.md"},
    {"name": "特性域-用例召回-agent", "path": "agents/特性域-用例召回-agent/特性域-用例召回-agent.md"},
    {"name": "问题域场景分析-类型分析-agent", "path": "agents/问题域场景分析-类型分析-agent/问题域场景分析-类型分析-agent.md"},
    {"name": "问题域场景分析-名称标准化-agent", "path": "agents/问题域场景分析-名称标准化-agent/问题域场景分析-名称标准化-agent.md"},
    {"name": "问题域场景分析-要素分析-agent", "path": "agents/问题域场景分析-要素分析-agent/问题域场景分析-要素分析-agent.md"},
    {"name": "系统域变更分析-模块变更分析-agent", "path": "agents/系统域变更分析-模块变更分析-agent/系统域变更分析-模块变更分析-agent.md"},
    {"name": "系统域变更分析-算法变更分析-agent", "path": "agents/系统域变更分析-算法变更分析-agent/系统域变更分析-算法变更分析-agent.md"},
    {"name": "系统域变更分析-子系统变更分析-agent", "path": "agents/系统域变更分析-子系统变更分析-agent/系统域变更分析-子系统变更分析-agent.md"},
    {"name": "系统域变更分析-组件变更分析-agent", "path": "agents/系统域变更分析-组件变更分析-agent/系统域变更分析-组件变更分析-agent.md"},
    {"name": "协议分析-agent", "path": "agents/协议分析-agent/协议分析-agent.md"},
    {"name": "智能需求规划-agent", "path": "agents/智能需求规划-agent/智能需求规划-agent.md"},
    {"name": "用例召回Agent", "path": "agents/用例召回Agent/usecase_recall_agent.md"},
    {"name": "知识搜索-agent", "path": "agents/知识搜索-agent/knowledge-search-agent.md"},
    {"name": "ReviewAgent", "path": "agents/ReviewAgent/review_agent.md"},
    {"name": "RootCauseAgent", "path": "agents/RootCauseAgent/root_cause_agent.md"},
    {"name": "SceneAnalysisAgent", "path": "agents/SceneAnalysisAgent/scene_analysis_agent.md"},
    {"name": "UserAnalysisAgent", "path": "agents/UserAnalysisAgent/user_analysis_agent.md"},
    {"name": "阶段3执行规则", "path": "rules/阶段3执行规则.md"},
    {"name": "全局规则", "path": "rules/全局规则.md"}
  ]
}

```

## 工作流（**严格按 agent 顺序，每个 agent 完整 find+detail**）

按 `By agent type` 顺序（已**按错误数降序**），**依次**对每个 agent 完整处理：
1. `find <sid> --agent-type <type>` 拿该 agent 的 hits
2. 对该 agent 的 hits **按 `failure_pattern` 去重**（**必须**对每个独特 pattern 至少 detail 一次）—— 选 1-2 个 uuid 看 T1→T4
3. 归因 + 匹配（结合 AGENT_ARCH）—— 该 agent 涉及的建议
4. 累积到 suggestions 列表
5. 继续下一个 agent（重复 1-4）

**所有 agent 处理完** → **写报告前**先**逐个**验证每个 unique failure_pattern 都 detail 过（**不**要写完才发现**漏**了）→ **写盘硬约束**：

- **必须**经 `python -c "import json, pathlib; ..."` 调 `json.dumps(report, ensure_ascii=False, indent=2)` 序列化后写盘（**不**用 Write 工具——避免内嵌双引号/反斜杠破坏 JSON）
- 写盘路径：`evidence/analysis_reports/5527b413-affc-443e-862f-15ff6bb3f7d1.analysis_report.json`
- 编码：`encoding='utf-8'`

## 完成后

最后一行输出 `<ANALYSIS_COMPLETE>` 或 `<ANALYSIS_FAILED>` + 原因。
