# 阶段 3 · Skill 进化

## 目标

跑 `see-evolve.py` 拿 bundle，按 bundle 内容调度 evolver sub-agent，**等它升级 target_file + 写 `evolution_report.json`**。

## 入口

```bash
PYTHONPATH=infra bash infra/scripts/with-python.sh infra/scripts/see-evolve.py <report.json> [skills_dir] [--evolved-skills-dir <dir>] [--output <bundle.json>]
```

参数：
- `<report.json>`：阶段 2 输出的 `analysis_report.json` 路径（必填）
- `skills_dir`：被进化的 skill / subagent 源目录（可选，缺省时 evolver 自己探测）

## 主 agent 跑这个阶段的步骤

1. **跑 see-evolve.py** 拿 bundle（stdout JSON）

2. **bundle 字段**（主 agent 必用）：
   - `report_path` — analysis_report.json 路径
   - `skills_dir` — 进化目标目录（可能为 null）
   - `evolved_skills_dir` — 进化后副本目录
   - `summary` — suggestions 摘要
   - `skill_search_paths` — 10 个候选探测路径（仅当 skills_dir 为 null 有效）
   - `prompt_template_path` — `prompts/evolver-prompt.md` 路径

3. **Read `bundle.prompt_template_path`**（= `prompts/evolver-prompt.md`）

4. **Agent 工具调 sub-agent**：
   - `type="general-purpose"`
   - `prompt=<Read 的内容>`
   - `tools=[Read, Write, Edit, Bash]`（Bash 调 patch_parser 必须走 `with-python.sh` 垫片）

5. **等 sub-agent 跑完**——evolver 改 target_file + 写 `evolution_report.json`

## 输出

- `evidence/evolution_reports/<session_id>.evolution_report.json`（待实现，目前见-evolve.py 不强制路径）
- `bundle.evolved_skills_dir/<target_file>` 副本
- 原位 `skills_dir/{target_file}` 升级

## 完成条件

- sub-agent 报告 `<EVOLUTION_COMPLETE>`（不是 `<EVOLUTION_FAILED>`）
- 至少 1 个 suggestion 升级成功（`status: "applied"` 或 `"fallback_to_full_file"`）

## 失败模式

| 现象 | 解决 |
|---|---|
| `report not found` | 跑阶段 2 生成 analysis_report.json |
| `skills_dir 不是目录` | 传正确的 skills_dir 或让 evolver 自己探测 |
| `锚点行未找到` | evolver 自动回退到"完整文件"模式 |
| 大量 `<EVOLUTION_FAILED>` | 看 `evolution_report.json` 详情；可重跑 |
