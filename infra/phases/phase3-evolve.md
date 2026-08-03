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

2. **调度规则（loop-fire）**：fire 与 await 交替——每次尝试 fire 一个新 sub-agent；fire 不下时 await 一个已完成释放槽位，**永不阻塞**。

```python
targets = json.loads(evolve_discovery.stdout)["targets"]
pending_fires = []                  # [(target, task_id), ...] 已 fire 未 await
done = set()

while len(done) < len(targets):
    # 1. 还有未 fire 的 → fire 一个
    if len(pending_fires) + len(done) < len(targets):
        target = next_unfired()
        call = json.loads(see_evolve_py(target))      # CLI 轻量
        task_id = Agent(
            description=call["description"],
            subagent_type=call["subagent_type"],
            run_in_background=call["run_in_background"],
            prompt=call["prompt"],
        )
        pending_fires.append((target, task_id))
        continue                                          # 立刻回到 loop 头

    # 2. 全部 fire 中 → await 最早的一个，释放槽位
    if pending_fires:
        target, task_id = pending_fires.pop(0)
        TaskOutput(task_id=task_id, block=True, timeout=600000)
        done.add(target)

# 循环结束：所有 target 已处理
```

3. **`see-evolve.py <subject_name> <target_file> --run-id <id>`** stdout 是 4 字段 JSON（description / subagent_type / run_in_background / prompt），**原样**传给 Agent——**不要**手写 prompt 或改 subagent_type。

4. 循环结束后**跑 `see-evolve-finalize.py --run-id <id>`** 把 `.change` 批量入库 review_db。

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
