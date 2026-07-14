# 阶段 3 · Skill 进化

## 目标

先 discovery 拿 target_files[]，再**逐个** target_file 跑 `see-evolve.py` 拿 4 字段 Agent 调用配置，调度 evolver sub-agent，**等它把升级后的完整文件写到 `.change`**。

> **不改原文件**：evolver 不做原位升级、不写 patch，只把**完整最终态**写到 `evidence/evolution_changes/<flatten>.change`。是否用 `.change` 覆盖原文件由后续人工/独立步骤决定。

## 入口（两个脚本）

```bash
# discovery：列出所有待进化的 target_file
PYTHONPATH=infra bash infra/scripts/with-python.sh infra/scripts/evolve-discovery.py [--reports-dir <dir>]

# per-target_file：拿单个 target_file 的 4 字段 Agent 调用配置
PYTHONPATH=infra bash infra/scripts/with-python.sh infra/scripts/see-evolve.py <target_file> [--skills-dir <dir>] [--change-output-dir <dir>] [--reports-dir <dir>]
```

参数：
- `<target_file>`：相对路径（如 `skills/查询需求信息/SKILL.md`），**必填**
- `--skills-dir`：skills 根目录（默认 `skills/`，sub-agent 用来 Read 原文件）
- `--change-output-dir`：`.change` 输出目录（默认 `evidence/evolution_changes/`）
- `--reports-dir`：`analysis_reports` 目录（默认 `evidence/analysis_reports/`，脚本从这里读 suggestions）

## 主 agent 跑这个阶段的步骤

1. **跑 `evolve-discovery.py`** → stdout JSON `{"target_files": ["skills/.../SKILL.md", ...]}`

2. **逐个 target_file 跑 `see-evolve.py <tf>`** → 每次拿一个 **4 字段 JSON**（脚本已算好 suggestions + prompt + `.change` 路径）：
   ```json
   {
     "description": "Evolve <target_file> (N suggestions)",
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

- `evidence/evolution_changes/<flatten_target_file>.change`（每个 target_file 一份，内容 = 升级后的**完整文件**）
  - 文件名扁平化：`skills/查询需求信息/SKILL.md` → `skills__查询需求信息__SKILL.md.change`
  - 原文件 `skills_dir/{target_file}` 保持不动，只写 `.change`

## 完成条件

- sub-agent 输出 `<EVOLUTION_COMPLETE>`（不是 `<EVOLUTION_FAILED>`）
- 对应的 `evidence/evolution_changes/<flatten>.change` 已生成

## 失败模式

| 现象 | 解决 |
|---|---|
| discovery `target_files` 为空 | 跑阶段 2 生成 `analysis_report.json`（里面要有含 `target_file` 的 suggestions） |
| `file_not_found`（原文件不存在） | 传正确的 `--skills-dir`，或确认 target_file 相对路径正确 |
| 某 target_file `<EVOLUTION_FAILED>` | 错误隔离——单个失败不影响其他；看该 sub-agent 输出的原因，可单独重跑 `see-evolve.py <tf>` |
