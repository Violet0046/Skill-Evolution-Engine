# 阶段 2 · 失败分析

> **主 agent 流程**（判断阶段、跑脚本 + 调度 sub-agent、同步用户）

## 阶段完成标志

| 阶段 | 标志 |
|---|---|
| 阶段 1 已完成 | `evidence/projects-simplified/<session_id>.jsonl` 存在 |
| 阶段 2 已完成 | `evidence/analysis_reports/<session_id>.analysis_report.json` 存在 |
| 阶段 3 已完成 | `evidence/evolution_reports/<session_id>.evolution_report.json` 存在 |

主 agent 跑阶段 2 前**自动**检查阶段 1 标志——**未**完成则**先**补跑（**不**跳过）。

## 入口

```bash
PYTHONPATH=infra bash infra/scripts/with-python.sh infra/scripts/see-analyze.py <session_id> [--root <dir>] [--output <prompt.md>]
```

参数：
- `<session_id>`：必填
- `--root`：简化版数据根目录（默认 `evidence/projects-simplified`）
- `--output`：可选，prompt 写到文件（默认 stdout）

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

## see-analyze.py 内部流程

```
1. 跑 see_failure_overview（写 .index/ 索引）
2. 调 core.util.resolve_architecture（用 session_id 拿 arch 路径）
3. 读 prompts/analyzer-prompt.md 模板
4. 读 rules/analyzer-agent-rules.md 规则
5. 读 arch JSON
6. 替换 5 个占位符：{{RULES}} / {{REPORT_PATH}} / {{AGENT_ARCH}} / {{OVERVIEW_SUMMARY}} / {{SESSION_ID}}
7. 输出完整 prompt 字符串到 stdout
```
