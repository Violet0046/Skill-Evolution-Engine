分析指定 session 的失败模式（阶段 2：analyzer agent 准备 + 数据预热）。

用户输入: $ARGUMENTS

## 执行步骤

### 步骤 1：解析参数
从用户输入中提取：
- `session_id`：session UUID（必填）
- `root`：简化版数据根目录（可选）

### 步骤 2：执行

工作目录为 Skill-Evolution-Engine 项目根：

```bash
PYTHONPATH=infra python infra/scripts/see-analyze.py {session_id} [--root <dir>] [--output <bundle.json>]
```

CLI 会：
1. 校验 session 存在
2. 预热失败索引（懒构建）
3. 输出一份 `analyzer_bundle.json`，含 analyzer 提示词 + 3 个 `see_*` tool schemas

### 步骤 3：调度 analyzer sub-agent
主 agent 拿到 bundle 后，调用 sub-agent：

```
Agent(
  type="general-purpose",
  prompt=bundle.analyzer_prompt,    # 已填好 session_id
  tools=bundle.tool_schemas,        # 3 个 see_*
)
```

sub-agent 跑完后写 `analysis_report.json`。

### 步骤 4：显示结果
显示脚本输出（bundle JSON），不添加额外内容。

## 执行规则
- 只执行脚本，不输出额外解释
- 不询问用户确认
- 执行完成后停止
- 使用中文回答
