# 阶段 3 · Skill 进化

## 目标

先 discovery 拿 `targets[]`（每项 = `{subject_name, target_file}`），再**逐个** target 跑 `see-evolve.py <subject_name> <target_file> --run-id <id>` 拿 4 字段 Agent 调用配置，调度 evolver sub-agent，**等它把升级后的完整文件写到 `.change`**。

> **不改原文件**：evolver 不做原位升级、不写 patch，只把**完整最终态**写到 `evidence/<run_id>/evolution_changes/<subject_name>__<flatten>.change`。是否用 `.change` 覆盖原文件由后续人工/独立步骤决定。

## 入口（两个脚本）

```bash
# discovery：列出所有待进化的 (subject_name, target_file)
PYTHONPATH=infra bash infra/scripts/with-python.sh infra/scripts/evolve-discovery.py --run-id <id>

# per-target：拿单个 (subject_name, target_file) 的 4 字段 Agent 调用配置
PYTHONPATH=infra bash infra/scripts/with-python.sh infra/scripts/see-evolve.py <subject_name> <target_file> --run-id <id>
```

参数：
- `<subject_name>`：subject 名（= arch 文件名 stem，discovery 输出的 `targets[].subject_name`），**必填**
- `<target_file>`：相对项目根的路径（如 `skills/查询需求信息/SKILL.md`），**必填**
- `--run-id`：本次运行 run_id（**必填**，从阶段 1 stdout 解析得到；不传直接报错）
- `--projects-home`：subjects 根目录（默认 `SEE_PROJECTS_HOME` env 或 `<engine>/subjects`；`project_root = <projects_home>/<subject_name>`）
- `--change-output-dir`：`.change` 输出目录（默认 `evidence/<run_id>/evolution_changes/`）
- `--reports-dir`：`analysis_reports` 目录（默认 `evidence/<run_id>/analysis_reports/`，脚本从这里按 subject+target 读 suggestions）

## 主 agent 跑这个阶段的步骤

1. **跑 `evolve-discovery.py --run-id <id>`** → stdout JSON `{"run_id": "...", "targets": [{"subject_name": "...", "target_file": "..."}, ...]}`

2. **逐个 target 跑 `see-evolve.py <subject_name> <target_file> --run-id <id>`** → 每次拿一个 **4 字段 JSON**（脚本已算好 suggestions + prompt + 绝对源路径 + `.change` 路径）：
   ```json
   {
     "description": "Evolve <subject_name>/<target_file> (N suggestions)",
     "subagent_type": "general-purpose",
     "run_in_background": true,
     "prompt": "# evolver agent\n...（完整 prompt，占位符已填）"
   }
   ```

3. **用 4 字段 JSON 原样调 Agent**（**不要**手写 prompt、**不要**改 `subagent_type`）：
   - `type=call["subagent_type"]`（已硬编码 `general-purpose`）
   - `run_in_background=call["run_in_background"]`（已硬编码 `true`）
   - `prompt=call["prompt"]`
   - `tools=[Read, Write]`（evolver 只 Read 原文件 + Write `.change`，**不需要** Bash/patch）
   - 逐个 fire——`run_in_background=true` 让 sub-agent 后台并发跑，主 agent 一次只发 1 个 prompt（避免上下文爆炸）

4. **循环外统一等所有 sub-agent 完成**（`TaskOutput` block）——evolver 把完整最终态写到 `.change`

## 输出

- `evidence/<run_id>/evolution_changes/<subject_name>__<flatten_target_file>.change`（每对 subject/target 一份，内容 = 升级后的**完整文件**）
  - 文件名 = subject 前缀 + 路径扁平化：`(需求分析Agent, skills/查询需求信息/SKILL.md)` → `需求分析Agent__skills__查询需求信息__SKILL.md.change`
  - 原文件 `<project_root>/<target_file>` 保持不动，只写 `.change`

## 完成条件

- sub-agent 输出 `<EVOLUTION_COMPLETE>`（不是 `<EVOLUTION_FAILED>`）
- 对应的 `evidence/evolution_changes/<subject_name>__<flatten>.change` 已生成

## 失败模式

| 现象 | 解决 |
|---|---|
| discovery `targets` 为空 | 跑阶段 2 生成 `analysis_report.json`（里面要有含 `subject_name` + `target_file` 的 suggestions） |
| `file_not_found`（原文件不存在） | 确认 `subjects/<subject_name>/<target_file>` 存在，或传正确的 `--projects-home` |
| 某 target `<EVOLUTION_FAILED>` | 错误隔离——单个失败不影响其他；看该 sub-agent 输出的原因，可单独重跑 `see-evolve.py <subject_name> <target_file>` |
