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

## 两种执行模式

阶段 2 由主 agent 调度，支持两种执行模式——根据**用户输入是否含 session_id** 区分：

### 模式 A · 单 session 模式（显式指定）

**触发**：用户 `/see-analyze <sid>` 或自然语言明确给出 session_id（如"分析 5527b413..."）

**主 agent 职责**：

1. 执行 `see-analyze.py <sid>` 一次，拿到 sub-agent prompt
2. 调一次 `Agent()` sub-agent
3. 验证 `analysis_reports/<sid>.analysis_report.json` 生成

### 模式 B · 批处理模式（默认，无 session_id）

**触发**：用户 `/see-analyze`（无参数）或自然语言"分析所有" / "批处理" / "跑阶段 2 batch"

**前提**：阶段 1 已完成，且 stdout 含 `session_ids` 字段

**主 agent 职责**：

1. 解析阶段 1 stdout JSON 的 `session_ids[]`
2. 对每个 sid **并行**（一次性 fire，sub-agent 后台运行）：

   - 执行 `see-analyze.py <sid>` 拿到 prompt
   - 调一次 `Agent()` sub-agent
   - 验证 `analysis_reports/<sid>.analysis_report.json` 生成

3. 全部完成后报告 N 处理 / N 失败

**会话契约**：`session_ids` 是阶段 1 输出的**唯一批量入口**——主 agent 不再自行 glob `evidence/projects-simplified/*.jsonl`，全部从阶段 1 stdout 读取。

**并行而非串行**：每个 sub-agent **上下文完全独立**（独立 arch、独立失败索引、独立 `analysis_reports/<sid>.jsonl`），任务间**无共享状态、无依赖**。主 agent 一次性 fire N 个 sub-agent（`Agent()` 默认后台运行），等所有完成再汇总。

**错误隔离**：单个 sub-agent 失败不影响其他——主 agent 只需检查每个 `analysis_reports/<sid>.analysis_report.json` 是否存在 + 报告数，对失败 sid 单独标记。

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
