# 阶段 2 · 失败分析

> **主 agent 流程**（判断阶段、跑脚本 + 调度 sub-agent、同步用户）

## 阶段完成标志

| 阶段 | 标志 |
|---|---|
| 阶段 1 已完成 | `evidence/<run_id>/projects-simplified/<session_id>.jsonl` 存在 |
| 阶段 2 已完成 | `evidence/<run_id>/analysis_reports/<session_id>.analysis_report.json` 存在 |
| 阶段 3 已完成 | `evidence/evolution_changes/<flatten_target_file>.change` 存在 |

主 agent 跑阶段 2 前**自动**检查阶段 1 标志——**未**完成则**先**补跑（**不**跳过）。

## 入口

```bash
PYTHONPATH=infra bash infra/scripts/with-python.sh infra/scripts/see-analyze.py <session_id> --run-id <id> [--output <prompt.md>]
```

参数：

- `<session_id>`：必填
- `--run-id`：本次运行 run_id（**必填**，从阶段 1 stdout 解析得到；不传直接报错）
- `--output`：可选，prompt 写到文件（默认 stdout）

## 两种执行模式

阶段 2 由主 agent 调度，支持两种执行模式——根据**用户输入是否含 session_id** 区分：

### 模式 A · 单 session 模式（显式指定）

**触发**：用户 `/see-analyze <sid>` 或自然语言明确给出 session_id（如"分析 5527b413..."）

**主 agent 职责**：

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

3. 验证 `evidence/<run_id>/analysis_reports/<sid>.analysis_report.json` 生成

### 模式 B · 批处理模式（默认，无 session_id）

**触发**：用户 `/see-analyze`（无参数）或自然语言"分析所有" / "批处理"

**前提**：阶段 1 已完成，且 stdout 含 `session_ids` 字段

**调度规则（loop-fire）**：fire 与 await 交替——每次尝试 fire 一个新 sub-agent；fire 不下时 await 一个已完成释放槽位，**永不阻塞**。

```python
session_ids = [...]                # 阶段 1 stdout 的 session_ids[]
pending_fires = []                  # [(sid, task_id), ...] 已 fire 未 await
done = set()

while len(done) < len(session_ids):
    # 1. 还有未 fire 的 → fire 一个
    if len(pending_fires) + len(done) < len(session_ids):
        sid = next_unfired()
        call = json.loads(see_analyze_py(sid))          # CLI 轻量
        task_id = Agent(
            description=call["description"],
            subagent_type=call["subagent_type"],
            run_in_background=call["run_in_background"],
            prompt=call["prompt"],
        )
        pending_fires.append((sid, task_id))
        continue                                          # 立刻回到 loop 头

    # 2. 全部 fire 中 → await 最早的一个，释放槽位
    if pending_fires:
        sid, task_id = pending_fires.pop(0)
        TaskOutput(task_id=task_id, block=True, timeout=600000)
        done.add(sid)

# 循环结束
report(N 处理 / N 失败)
```

**主 agent 职责**：

1. 解析阶段 1 stdout JSON 的 `session_ids[]`
2. 按 loop-fire 伪代码循环
3. 循环结束后验证 `evidence/<run_id>/analysis_reports/<sid>.analysis_report.json` 是否都生成
4. 报告 N 处理 / N 失败

**会话契约**：`session_ids` 是阶段 1 输出的**唯一批量入口**——主 agent 不再自行 glob 简化版目录下的 jsonl，全部从阶段 1 stdout 读取。

**sub-agent 隔离**：每个 sub-agent **上下文完全独立**（独立 arch、独立失败索引、独立 `analysis_reports/<sid>.jsonl`），任务间**无共享状态、无依赖**。

**错误隔离**：单个 sub-agent 失败不影响其他——主 agent 只需检查每个 `analysis_reports/<sid>.analysis_report.json` 是否存在 + 报告数，对失败 sid 单独标记。

## 完成条件

- `evidence/<run_id>/analysis_reports/<session_id>.analysis_report.json` 文件存在（sub-agent 用 Write 写到这）
- sub-agent 报告 `<ANALYSIS_COMPLETE>`（不是 `<ANALYSIS_FAILED>`）
- 报告里 `suggestions` 字段非空

## 失败模式

| 现象 | 解决 |
|---|---|
| `arch 不存在`（exit code 1） | AskUserQuestion 问用户 agent 名（让用户建 `agent-architectures/<basename>.json`）|
| `session not found` | 跑阶段 1 重新生成 |
| `<ANALYSIS_FAILED>` | 看 `analysis_report.json` 的 `error` 字段；可重跑 sub-agent |

## see-analyze.py 内部流程

```text
1. 跑 see_failure_overview（写 .index/ 索引）
2. 调 core.util.resolve_architecture（用 session_id 拿 arch 路径）
3. 读 prompts/analyzer-prompt.md 模板
4. 读 rules/analyzer-agent-rules.md 规则
5. 读 arch JSON
6. 替换模板中的 5 个占位符（{{RULES}} / {{AGENT_ARCH}} / {{OVERVIEW_SUMMARY}} / {{SUBJECT_NAME}} / {{SESSION_ID}}）
7. 硬编码 subagent_type="general-purpose" + run_in_background=true
8. 构造 4 字段 JSON：{description, subagent_type, run_in_background, prompt}
9. 输出 JSON 字符串到 stdout
```
