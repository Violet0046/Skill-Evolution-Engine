# 阶段 2 · 失败分析

## 目标

主 agent 调 `see-analyze.py` **直接拿完整 sub-agent prompt** —— 把 prompt 传给 Agent 工具的 `prompt` 参数即可。

## 入口

```bash
PYTHONPATH=infra bash infra/scripts/with-python.sh infra/scripts/see-analyze.py <session_id> [--root <dir>] [--output <prompt.md>]
```

参数：
- `<session_id>`：必填
- `--root`：简化版数据根目录（默认 `evidence/projects-simplified`）
- `--output`：可选，prompt 写到文件（默认 stdout）

## 主 agent 跑这个阶段的步骤

1. **跑 `see-analyze.py`** 拿完整 prompt 字符串（**唯一**外部调用）
2. **Agent 工具调 sub-agent**：
   - `type="general-purpose"`
   - `prompt=<see-analyze.py 的 stdout>`
   - `tools=["Bash", "Write"]`（sub-agent 用 Bash 调 see_* CLI，详见提示词 `## 工具集` 段）

## see-analyze.py 内部流程（**主 agent 不感知**）

```
1. 跑 see_failure_overview（拿 4 字段 bundle + 写 .index/ 索引）
2. 调 core.util.resolve_architecture（用 session_id 拿 arch 路径）
3. 读 prompts/analyzer-prompt.md 模板
4. 读 rules/analyzer-agent-rules.md 规则
5. 读 arch JSON
6. 替换 5 个占位符：{{RULES}} / {{REPORT_PATH}} / {{AGENT_ARCH}} / {{OVERVIEW_SUMMARY}} / {{SESSION_ID}}
7. 输出完整 prompt 字符串到 stdout
```

## 输出

stdout 输出：完整 sub-agent prompt 字符串（**主 agent**直接作为 Agent 工具的 `prompt` 参数）

## 完成条件

- `evidence/analysis_reports/<session_id>.analysis_report.json` 文件存在（sub-agent 用 Write 写到这）
- sub-agent 报告 `<ANALYSIS_COMPLETE>`（不是 `<ANALYSIS_FAILED>`）
- 报告里 `suggestions` 字段非空

## 失败模式

| 现象 | 解决 |
|---|---|
| `arch 不存在`（exit code 1） | AskUserQuestion 问用户 agent 名（让用户建 `agent-architectures/<basename>.json`）|
| `session not found` | 跑阶段 1 重新生成 |
| `<ANALYSIS_FAILED>` | 看 `analysis_report.json` 的 `error` 字段；可重跑 sub-agent |
