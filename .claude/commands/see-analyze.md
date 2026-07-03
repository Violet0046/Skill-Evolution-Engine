分析指定 session 的失败模式（阶段 2：拼装 sub-agent 完整 prompt + 调 sub-agent）。

用户输入: $ARGUMENTS

## 执行步骤

### 步骤 1：解析参数
从用户输入中提取：
- `session_id`：session UUID（必填）
- `root`：简化版数据根目录（可选）

### 步骤 2：跑脚本拿 sub-agent 完整 prompt

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

### 步骤 3：调 Agent 工具启动 sub-agent

把 stdout 作为 sub-agent 的 prompt：

```python
Agent(
    type="general-purpose",
    prompt=<步骤 2 的 stdout>,
    tools=["Bash", "Write"],   # sub-agent 用 Bash 调 see_* CLI（走 with-python.sh 垫片），用 Write 写 analysis_report.json
)
```

sub-agent 会**自动**：
- 按 prompt 工作流工作（按 agent 遍历 find/detail）
- 调 `Write` 工具把 `analysis_report.json` 写到 `evidence/analysis_reports/<session_id>.analysis_report.json`
- 输出 `<ANALYSIS_COMPLETE>` / `<ANALYSIS_FAILED>`

## 执行规则
- 只执行脚本，不输出额外解释
- 不询问用户确认
- 执行完成后停止
- 使用中文回答
