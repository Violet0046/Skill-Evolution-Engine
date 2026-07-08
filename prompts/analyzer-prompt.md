# analyzer agent

**任务**：调用 2 个 `see_*` 工具分析当前 session，输出 `evidence/analysis_reports/{{SESSION_ID}}.analysis_report.json`。

## 报告 schema

`<session_id>.analysis_report.json` 的 JSON 结构：

```json
{
  "session_id": "{{SESSION_ID}}",
  "generated_at": "<ISO timestamp>",
  "suggestions": [
    {
      "id": "{{SESSION_ID}}-sg-001",
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

{{OVERVIEW_SUMMARY}}

## 规则

{{RULES}}

## AGENT_ARCH

下面是该 agent 项目的可改文件清单（`target_skill` / `target_file` **优先**从中选）：

```json
{{AGENT_ARCH}}
```

## 工作流（**严格按 agent 顺序，每个 agent 完整 find+detail**）

按 `By agent type` 顺序（已**按错误数降序**），**依次**对每个 agent 完整处理：
1. `find <sid> --agent-type <type>` 拿该 agent 的 hits
2. 对该 agent 的 hits **按 `failure_pattern` 去重**（**必须**对每个独特 pattern 至少 detail 一次）—— 选 1-2 个 uuid 看 T1→T4
3. 归因 + 匹配（结合 AGENT_ARCH）—— 该 agent 涉及的建议
4. 累积到 suggestions 列表
5. 继续下一个 agent（重复 1-4）

**所有 agent 处理完** → **写报告前**先**逐个**验证每个 unique failure_pattern 都 detail 过（**不**要写完才发现**漏**了）→ 用 Write 工具一次性写 `evidence/analysis_reports/<session_id>.analysis_report.json`

## 完成后

最后一行输出 `<ANALYSIS_COMPLETE>` 或 `<ANALYSIS_FAILED>` + 原因。
