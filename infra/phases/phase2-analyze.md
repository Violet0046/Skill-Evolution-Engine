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

**主 agent 职责**（**data-driven dispatch**）：

1. 执行 `see-analyze.py <sid>` 一次，stdout 是 **4 字段 JSON 配置**：

   ```json
   {
     "description": "Analyze session <sid>",
     "subagent_type": "general-purpose", 
     "run_in_background": true,
     "prompt": "# analyzer agent\n..."     // 完整 analyzer-prompt
   }
   ```

2. **解析 JSON**，用 JSON 字段直接调 `Agent()`（**不要**自己拼 prompt 或选 `subagent_type`）：

   ```python
   call = json.loads(<Bash stdout>)
   Agent(
       description=call["description"],
       subagent_type=call["subagent_type"],
       run_in_background=call["run_in_background"],
       prompt=call["prompt"],
   )
   ```

3. 验证 `analysis_reports/<sid>.analysis_report.json` 生成

### 模式 B · 批处理模式（默认，无 session_id）

**触发**：用户 `/see-analyze`（无参数）或自然语言"分析所有" / "批处理"

**前提**：阶段 1 已完成，且 stdout 含 `session_ids` 字段

**主 agent 职责**（**data-driven dispatch**）：

1. 解析阶段 1 stdout JSON 的 `session_ids[]`
2. 对每个 sid：

   - 跑 `see-analyze.py <sid>` 拿 4 字段 JSON
   - 解析 JSON

3. **逐个 fire**（**错开启动避免主 agent 上下文爆炸，但保留 sub-agent 后台并发**）：

   ```python
   # 假设 session_ids = ["uuid1", "uuid2", ...]
   task_ids = []
   for sid in session_ids:
       call = json.loads(<Bash stdout for sid>)  # 这个 sid 的 4 字段 JSON
       task_id = Agent(
           description=call["description"],
           subagent_type=call["subagent_type"],
           run_in_background=call["run_in_background"],
           prompt=call["prompt"],
       )
       task_ids.append(task_id)
       # ↑ fire 完立即返回 task_id，sub-agent 后台跑
   ```

4. **循环外**用 `TaskOutput` 等所有 sub-agent 完成：

   ```python
   # 全部 fire 完后再 await（**不**在循环里 await——那样会阻塞后续 sub-agent 启动）
   for task_id in task_ids:
       TaskOutput(task_id=task_id, block=true, timeout=600000)
   ```

5. 全部完成后报告 N 处理 / N 失败

**为什么"逐个 fire"而不是"同一 message fire N 个"**：

| 维度 | 同一 message N 个 | **逐个 fire（run_in_background）** |
|---|---|---|
| 主 agent outgoing message 大小 | **N × prompt_size**（**可能爆**）| **1 × prompt_size**（安全）|
| Sub-agent 并发数 | N（同时启动）| 逐渐增加（每 fire 一个 +1）|
| 总时间 | T_max | T_avg + (N-1)Δ/2 ≈ T_avg（Δ 很小）|
| 上下文安全 | ⚠️ N 大时爆 | ✅ 安全 |

> 核心：**保留 sub-agent 后台并发**（`run_in_background=true`）+ **错开启动时机**（主 agent outgoing message 一次只装 1 个 prompt）= 上下文安全 + 接近并行的速度。

**data-driven dispatch 的优势**：

- **`subagent_type` 硬编码为 `"general-purpose"`**——主 agent 不会再选错成 `"analyzer"`（项目里"analyzer"是逻辑角色名，Agent tool 不接受）
- **`run_in_background` 硬编码为 `true`**——主 agent 不会再忘加（默认是同步，会串行）
- **`prompt` 是脚本组装好的完整文本**——主 agent 不会再手写或递归构造（之前是"让 sub-agent 跑 see-analyze.py"的灾难）
- **主 agent 退化为 dispatch 循环**——几乎不可能出错

**会话契约**：`session_ids` 是阶段 1 输出的**唯一批量入口**——主 agent 不再自行 glob `evidence/projects-simplified/*.jsonl`，全部从阶段 1 stdout 读取。

**sub-agent 隔离**：每个 sub-agent **上下文完全独立**（独立 arch、独立失败索引、独立 `analysis_reports/<sid>.jsonl`），任务间**无共享状态、无依赖**。

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
7. 硬编码 subagent_type="general-purpose" + run_in_background=true
8. 构造 4 字段 JSON：{description, subagent_type, run_in_background, prompt}
9. 输出 JSON 字符串到 stdout
```
