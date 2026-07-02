基于 analysis_report.json 进化 skill（阶段 3：evolver agent 准备 + 输入校验）。

用户输入: $ARGUMENTS

## 执行步骤

### 步骤 1：解析参数
从用户输入中提取（自然语言描述也行，例如"进化报告在 X，技能目录是 Y"）：
- `analysis_report.json`：阶段 2 输出的报告路径（必填）
- `skills_dir`：被进化的 skill / subagent 源目录（**可选**）
  - 用户没指定 → 主 agent 自己用 `Bash find` / `Bash ls` 探测常见位置（见 main-agent-rules.md "skills_dir 探测"）
  - 探测不到 → 用 AskUserQuestion 问用户

### 步骤 2：检查报告
```bash
ls -la {analysis_report.json} 2>/dev/null || echo "报告不存在: {analysis_report.json}"
```

如果报告不存在，提示用户先执行 `/see-analyze {session_id}`。

### 步骤 3：执行

工作目录为 Skill-Evolution-Engine 项目根：

```bash
PYTHONPATH=infra bash infra/scripts/with-python.sh infra/scripts/see-evolve.py {analysis_report.json} [skills_dir] [--output <bundle.json>]
```

CLI 会：
1. 校验 report 存在
2. 校验 skills_dir（如传了）
3. 输出一份 `evolver_bundle.json`（stdout），含 `report_path` + `skills_dir` + `summary` + `prompt_template_path` + `skill_search_paths`

> **本命令的职责到此为止**——不调 sub-agent、不写 `evolution_report.json`、不改 target_file。sub-agent 调度由主 agent 按 CLAUDE.md「执行规则」负责。

### 步骤 4：调度 evolver sub-agent

> 本命令的"步骤 3"已把"职责边界"说清（不调 sub-agent）。具体 sub-agent 调度流程见 [CLAUDE.md](../CLAUDE.md)「3 阶段工作流的硬性调度链路」第 3 条。

### 步骤 5：显示结果
显示脚本输出（bundle JSON），不添加额外内容。

> 注：sub-agent 跑完后**主 agent**应主动输出 `evolution_report.json` 摘要，不在本命令职责内。

## 执行规则
- 只执行脚本，不输出额外解释
- 不询问用户确认
- 执行完成后停止
- 使用中文回答
