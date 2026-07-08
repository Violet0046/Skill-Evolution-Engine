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

#### 步骤 A.1：跑脚本拿 sub-agent 完整 prompt

工作目录为 Skill-Evolution-Engine 项目根：

```bash
PYTHONPATH=infra bash infra/scripts/with-python.sh infra/scripts/see-analyze.py {session_id} [--root <dir>] [--output <prompt.md>]
```

CLI 会：
1. 校验 session 存在
2. 预热失败索引（`.index/<session_id>.json`）
3. 读 `prompts/analyzer-prompt.md` 模板 + `rules/analyzer-agent-rules.md` 规则 + `agent-architectures/<basename>.json` 架构
4. 替换 5 个占位符（`{{RULES}}` / `{{REPORT_PATH}}` / `{{AGENT_ARCH}}` / `{{OVERVIEW_SUMMARY}}` / `{{SESSION_ID}}`）
5. 输出完整 sub-agent prompt 字符串到 stdout

#### 步骤 A.2：调 Agent 工具启动 sub-agent

把 stdout 作为 sub-agent 的 prompt：

```python
Agent(
    type="general-purpose",
    prompt=<步骤 A.1 的 stdout>,
    tools=["Bash", "Write"],   # sub-agent 用 Bash 调 see_* CLI（走 with-python.sh 垫片），用 Write 写 analysis_report.json
)
```

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

#### 步骤 B.2：并行 fire N 个 sub-agent（fan-out）

对 `session_ids[]` 里**每个 sid**：

1. 执行 `see-analyze.py <sid>` 拿 prompt：

   ```bash
   PYTHONPATH=infra bash infra/scripts/with-python.sh infra/scripts/see-analyze.py {sid} --output /tmp/prompt_{sid}.md
   ```

2. 调 `Agent()` sub-agent（**默认后台运行**，多个一次性 fire 实现并行）：

   ```python
   Agent(
       type="general-purpose",
       prompt=<Read /tmp/prompt_{sid}.md 的内容>,
       tools=["Bash", "Write"],
   )
   ```

> **并行而非串行**：每个 sub-agent 上下文完全独立（独立 arch、独立失败索引、独立 report 文件），无共享状态。`Agent()` 默认后台——一次性 fire N 个 + 等所有完成 = fan-out。

#### 步骤 B.3：汇总结果

等待所有 sub-agent 完成后，验证每个 sid 对应的 `analysis_reports/<sid>.analysis_report.json` 是否生成 + 报告数，统计：

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
