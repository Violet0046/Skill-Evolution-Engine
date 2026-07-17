分析指定 session 的失败模式（阶段 2：拼装 sub-agent 完整 prompt + 调 sub-agent）。

**支持两种模式**
- **单 session 模式**：用户提供具体 `<session_id>`
- **批处理模式**（默认）：用户无参数调用时，从阶段 1 stdout 解析 `session_ids[]` 并行处理

## 执行步骤

### 步骤 1：判断执行模式

检查 `$ARGUMENTS`：

- **含 session_id（UUID 格式）** → 进入**模式 A · 单 session 模式**
- **空 / 无 UUID** → 进入**模式 B · 批处理模式**

> **重要**：模式判断只看 $ARGUMENTS 是否**显式包含** UUID——**不要**从上下文、报告路径、之前输出里"猜"出 UUID 当 session_id。
> 如果 $ARGUMENTS 里同时夹杂其他文字（含 UUID），**只取 UUID**，其余视为无效。

---

### 模式 A · 单 session 模式

#### 步骤 A.1：跑脚本拿 Agent 调用配置（JSON）

工作目录为 Skill-Evolution-Engine 项目根：

```bash
PYTHONPATH=infra bash infra/scripts/with-python.sh infra/scripts/see-analyze.py {session_id} --run-id <id>
```

**stdout 是一个 4 字段 JSON 字符串**：

```json
{
  "description": "Analyze session <sid>",
  "subagent_type": "general-purpose",
  "run_in_background": true,
  "prompt": "# analyzer agent\n...（完整 prompt）"
}
```

CLI 内部：

1. 校验 session 存在
2. 预热失败索引（`.index/<session_id>.json`）
3. 读 `prompts/analyzer-prompt.md` 模板 + `rules/analyzer-agent-rules.md` 规则 + `agent-architectures/<basename>.json` 架构
4. 替换 6 个占位符
5. **硬编码** `subagent_type="general-purpose"` + `run_in_background=true`（避免主 agent 选错）
6. 输出 4 字段 JSON

#### 步骤 A.2：解析 JSON 后调 Agent（**不要手写 prompt**）

**关键**：从 JSON 取字段，**不要再手写** prompt 或选 subagent_type：

```python
# 1. 解析 Bash 工具返回的 JSON
agent_call = json.loads(<Bash stdout>)

# 2. 用 JSON 字段直接调 Agent
Agent(
    description=agent_call["description"],
    subagent_type=agent_call["subagent_type"],
    run_in_background=agent_call["run_in_background"],
    prompt=agent_call["prompt"],   # 完整的 analyzer-prompt
)
```

> **不要**用自己拼的 prompt 调 Agent——用 JSON 里的 `prompt` 字段原样传。
> **不要**改 `subagent_type` 字段——它已硬编码正确值。

sub-agent 会**自动**：

- 按 prompt 工作流工作（按 agent 遍历 find/detail）
- 把 `analysis_report.json` 写到 `evidence/<run_id>/analysis_reports/<session_id>.analysis_report.json`
- 输出 `<ANALYSIS_COMPLETE>` / `<ANALYSIS_FAILED>`

---

### 模式 B · 批处理模式（默认）

#### 步骤 B.1：拿 session_ids 列表

如果阶段 1 未跑（`evidence/<run_id>/projects-simplified/<sid>.jsonl` 不存在），**先**跑阶段 1：

```bash
PYTHONPATH=infra bash infra/scripts/with-python.sh infra/scripts/see-collect.py
```

从 stdout JSON 解析 `session_ids[]` 字段。

> 阶段 1 已跑过且 `session_ids` 已知 → **跳过**本步骤直接进 B.2。

#### 步骤 B.2：并行 see-analyze.py + 串行 fire-and-await

**核心调度原则**：两个阶段**并发策略不同**——`see-analyze.py` 这一步轻量可以并行，`Agent fire` + `TaskOutput await` 必须串行。

| 阶段 | 并发度 | 理由 |
| --- | --- | --- |
| 跑 `see-analyze.py` 拿 4 字段 JSON | **并行**（N 条 Bash 在同一 outgoing message） | CLI 轻量（几秒，stdout 5-7KB），并行不抢资源 |
| `Agent` fire + `TaskOutput` await | **批量 fire + 串行 await**（sub-agent 后台并行跑，主 agent 逐个处理结果） | 控制 context 增长线性化、失败定位一一对应、错误硬隔离 |

##### 阶段 1：**并行**跑 N 个 see-analyze.py

一个 outgoing message 里同时发 N 条 Bash，**并行**拿到 N 个 JSON：

```bash
PYTHONPATH=infra bash infra/scripts/with-python.sh infra/scripts/see-analyze.py <sid_1> --run-id <id>
PYTHONPATH=infra bash infra/scripts/with-python.sh infra/scripts/see-analyze.py <sid_2> --run-id <id>
...
PYTHONPATH=infra bash infra/scripts/with-python.sh infra/scripts/see-analyze.py <sid_N> --run-id <id>
```

拿到 N 个 JSON 字符串，**解析成列表备用**：

```python
call_list = [json.loads(s) for s in json_strings]
```

##### 阶段 2：**批量 fire + 串行 await**（sub-agent 并行跑，结果处理串行）

```python
# 第一阶段：批量 fire（**同一个 outgoing message 里 N 个 Agent 调用**——sub-agent 全部并行启动）
task_ids = []
for sid, call in zip(session_ids, call_list):
    task_id = Agent(
        description=call["description"],
        subagent_type=call["subagent_type"],
        run_in_background=call["run_in_background"],
        prompt=call["prompt"],
    )
    task_ids.append((sid, task_id))

# 第二阶段：串行 await（每个 sid 一个 TaskOutput——sub-agent 在后台并行跑，但 await 顺序处理结果）
for sid, task_id in task_ids:
    TaskOutput(task_id=task_id, block=True, timeout=600000)
```

> **不要**自己写 `subagent_type="general-purpose"` 或 `run_in_background=true`——直接用 JSON 里的字段。

#### 步骤 B.3：汇总结果

拿到所有 TaskOutput 结果后，验证每个 sid 对应的 `evidence/<run_id>/analysis_reports/<sid>.analysis_report.json` 是否生成 + 报告数，统计：

- **成功**：文件存在 + `suggestions` 非空
- **失败**：文件缺失 / sub-agent 报 `<ANALYSIS_FAILED>`
- **错误隔离**：单个失败不影响其他

输出汇总："批处理完成：N 成功 / M 失败 / session_ids 总数 K"。

## 执行规则

- 只执行脚本，不输出额外解释
- 不询问用户确认
- 执行完成后停止
- 使用中文回答
- 模式判断严格按 $ARGUMENTS，**不要**从上下文/历史输出推断 UUID
