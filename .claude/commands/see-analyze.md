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
PYTHONPATH=infra bash infra/scripts/with-python.sh infra/scripts/see-analyze.py {session_id} [--root <dir>]
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
4. 替换 5 个占位符
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
- 调 `Write` 工具把 `analysis_report.json` 写到 `evidence/analysis_reports/<session_id>.analysis_report.json`
- 输出 `<ANALYSIS_COMPLETE>` / `<ANALYSIS_FAILED>`

---

### 模式 B · 批处理模式（默认）

#### 步骤 B.1：拿 session_ids 列表

如果阶段 1 未跑（`evidence/projects-simplified/<sid>.jsonl` 不存在），**先**跑阶段 1：

```bash
PYTHONPATH=infra bash infra/scripts/with-python.sh infra/scripts/see-collect.py
```

从 stdout JSON 解析 `session_ids[]` 字段。

> 阶段 1 已跑过且 `session_ids` 已知 → **跳过**本步骤直接进 B.2。

#### 步骤 B.2：并行 fire N 个 sub-agent（**data-driven dispatch**）

**核心思路**：每个 sid 调一次 `see-analyze.py` 拿到 4 字段 JSON → 用 JSON 字段直接调 Agent。**不要**自己拼 Agent 调用参数。

##### 阶段 1：对每个 sid 调 see-analyze.py，拿到 JSON

```bash
PYTHONPATH=infra bash infra/scripts/with-python.sh infra/scripts/see-analyze.py {sid}
```

stdout 是一个 4 字段 JSON（见步骤 A.1 的格式说明）。**对每个 sid 都跑一次**——拿到 N 个 JSON 字符串，**记住**（或塞进一个列表里）。

##### 阶段 2：**逐个 fire**

> **逐个 fire** = 主 agent 一次 outgoing message 只有 1 个 prompt（避免上下文爆炸），但 N 个 sub-agent 在**后台并发跑**

**循环**对每个 sid 调 Agent + TaskOutput：

```python
# 拿到 N 个 sid 的 JSON（可以预先放在一个列表里）
# 例如：call_list = [json.loads(s) for s in json_strings]

task_ids = []
for sid in session_ids:
    # 拿这个 sid 的 4 字段 JSON
    call = json.loads(<Bash stdout for sid>)  # 或从 call_list 取

    # fire Agent（**立即返回 task_id**，sub-agent 后台跑）
    task_id = Agent(
        description=call["description"],
        subagent_type=call["subagent_type"],
        run_in_background=call["run_in_background"],
        prompt=call["prompt"],
    )
    task_ids.append(task_id)
```

> **不要**自己写 `subagent_type="general-purpose"` 或 `run_in_background=true`——直接用 JSON 里的字段。
> **不要**在循环里调 TaskOutput——**循环外**统一等所有完成（这样后续 sub-agent 可以**继续后台跑**直到我们 await）。

##### 阶段 3：用 `TaskOutput` 等所有 sub-agent 完成

**循环外**对每个 `task_id` **阻塞等结果**：

```python
# 现在 await 所有 sub-agent
for task_id in task_ids:
    TaskOutput(task_id=task_id, block=true, timeout=600000)
```

> 之所以"循环外 await"而不是"循环内 fire-and-await"——后者会让后续 sub-agent 的启动**被前面的 await 阻塞**，失去并发收益。

#### 步骤 B.3：汇总结果

拿到所有 TaskOutput 结果后，验证每个 sid 对应的 `analysis_reports/<sid>.analysis_report.json` 是否生成 + 报告数，统计：

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
