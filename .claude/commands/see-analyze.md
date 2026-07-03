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
PYTHONPATH=infra bash infra/scripts/with-python.sh infra/scripts/see-analyze.py {session_id} [--root <dir>] [--output <bundle.json>]
```

CLI 会：
1. 校验 session 存在
2. 预热失败索引（懒构建）
3. 输出一份 `analyzer_bundle.json`（stdout），含 `session_id` + `agent_cwd` + `summary` + `by_agent_type`

> **本命令的职责到此为止**——不调 sub-agent、不写 analysis_report.json。sub-agent 调度由主 agent 按 CLAUDE.md「执行规则」负责。

## 执行规则
- 只执行脚本，不输出额外解释
- 不询问用户确认
- 执行完成后停止
- 使用中文回答
