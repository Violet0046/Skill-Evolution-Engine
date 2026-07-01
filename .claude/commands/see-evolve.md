基于 analysis_report.json 进化 skill（阶段 3：evolver agent 准备 + 输入校验）。

用户输入: $ARGUMENTS

## 执行步骤

### 步骤 1：解析参数
从用户输入中提取：
- `analysis_report.json`：阶段 2 输出的报告路径（必填）
- `skills_dir`：被进化的 skill 源目录（必填）

### 步骤 2：检查报告
```bash
ls -la {analysis_report.json} 2>/dev/null || echo "报告不存在: {analysis_report.json}"
```

如果报告不存在，提示用户先执行 `/see-analyze {session_id}`。

### 步骤 3：执行

工作目录为 Skill-Evolution-Engine 项目根：

```bash
PYTHONPATH=infra python infra/scripts/see-evolve.py {analysis_report.json} {skills_dir} [--output <bundle.json>]
```

CLI 会：
1. 校验 report + skills_dir
2. 输出一份 `evolver_bundle.json`，含 evolver 提示词 + suggestions 摘要

### 步骤 4：调度 evolver sub-agent
主 agent 拿到 bundle 后，调用 sub-agent：

```
Agent(
  type="general-purpose",
  prompt=bundle.evolver_prompt,
  tools=[Read, Write, Edit, Bash],   # patch_parser 走 Bash
)
```

sub-agent 跑完后输出 `evolution_report.json`，SKILL.md 已升级。

### 步骤 5：显示结果
显示脚本输出（bundle JSON），不添加额外内容。

## 执行规则
- 只执行脚本，不输出额外解释
- 不询问用户确认
- 执行完成后停止
- 使用中文回答
