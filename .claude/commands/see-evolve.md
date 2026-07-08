进化 SKILL.md 文件（阶段 3：按 target_file 升级 + 写 evolution_report.json）。

**支持两种模式**（与 [main-agent-rules.md](../../rules/main-agent-rules.md) 和 [phase3-evolve.md](../../infra/phases/phase3-evolve.md) 一致）：
- **单 target_file 模式**：用户提供具体 `<target_file>` 路径
- **批处理模式**（默认）：无参数调用时，按 target_file 聚合所有 analysis_reports，逐个 fire Agent 进化

## 执行步骤

### 步骤 1：判断执行模式

检查 `$ARGUMENTS`：

- **含 target_file（路径格式）** → 进入**模式 A · 单 target_file 模式**
- **空** → 进入**模式 B · 批处理模式**

> 模式判断只看 $ARGUMENTS 是否**显式包含** target_file——**不要**从上下文、历史输出"猜"。

---

### 模式 A · 单 target_file 模式

#### 步骤 A.1：跑脚本拿 Agent 调用配置（JSON）

工作目录为 Skill-Evolution-Engine 项目根：

```bash
PYTHONPATH=infra bash infra/scripts/with-python.sh infra/scripts/see-evolve.py {target_file} [--skills-dir <path>] [--evolved-skills-dir <path>]
```

**stdout 是一个 4 字段 JSON 字符串**（不是裸 prompt！）：

```json
{
  "description": "Evolve <target_file> (N suggestions)",
  "subagent_type": "general-purpose",
  "run_in_background": true,
  "prompt": "# evolver agent · per-target_file\n...（完整 prompt）"
}
```

CLI 内部：

1. 扫 `evidence/analysis_reports/*.analysis_report.json` 找这个 target_file 的 suggestions
2. 过滤 priority（high > medium，**low 跳过**）
3. 读 `prompts/evolver-prompt.md` 模板 + `rules/evolver-agent-rules.md` 规则
4. 替换 6 个占位符（`{{RULES}}` / `{{TARGET_SKILL}}` / `{{TARGET_FILE}}` / `{{SKILLS_DIR}}` / `{{EVOLVED_SKILLS_DIR}}` / `{{SUGGESTIONS_JSON}}`）
5. **硬编码** `subagent_type="general-purpose"` + `run_in_background=true`（避免主 agent 选错）
6. 输出 4 字段 JSON

#### 步骤 A.2：解析 JSON 后调 Agent（**不要手写 prompt**）

```python
# 1. 解析 Bash 工具返回的 JSON
agent_call = json.loads(<Bash stdout>)

# 2. 用 JSON 字段直接调 Agent
Agent(
    description=agent_call["description"],
    subagent_type=agent_call["subagent_type"],
    run_in_background=agent_call["run_in_background"],
    prompt=agent_call["prompt"],
)
```

> **不要**用自己拼的 prompt 调 Agent——用 JSON 里的 `prompt` 字段原样传。
> **不要**改 `subagent_type` 字段——它已硬编码正确值。

#### 步骤 A.3：等结果 + 验证

```python
TaskOutput(task_id=<id>, block=true, timeout=600000)
```

sub-agent 会：

- 读 `skills_dir/target_file`（如果不存在 → 报 `file_not_found`）
- 逐条应用 suggestions（按 priority 排序）
- 写 `evidence/evolution_reports/<target_file_safe>.evolution_report.json`
- 输出 `<EVOLUTION_COMPLETE>` / `<EVOLUTION_FAILED>`

---

### 模式 B · 批处理模式（默认）

#### 步骤 B.1：拿所有 target_file 列表

```bash
PYTHONPATH=infra bash infra/scripts/with-python.sh infra/scripts/see-evolve-aggregate.py
```

stdout JSON 含 `target_files[]`（每个 entry = `{target_skill, target_file, suggestion_count, suggestions[]}`）。

#### 步骤 B.2：**逐个 fire**（data-driven dispatch，逐个 target_file）

> **关键洞察**：`run_in_background=true` 让 sub-agent **后台跑**——主 agent 不用等它完成才发下一个。
> **逐个 fire** = 主 agent 一次 outgoing message 只有 1 个 prompt（避免上下文爆炸），但 N 个 sub-agent 在**后台并发跑**。

```python
# 拿到 target_files 列表（来自步骤 B.1）
agg = json.loads(<Bash stdout from see-evolve-aggregate.py>)
target_files = [tf["target_file"] for tf in agg["target_files"]]

# 循环：对每个 target_file 调 see-evolve.py + 拿 4 字段 JSON + fire Agent
task_ids = []
for tf in target_files:
    call = json.loads(<Bash stdout from see-evolve.py tf>)  # 4 字段 JSON

    task_id = Agent(
        description=call["description"],
        subagent_type=call["subagent_type"],
        run_in_background=call["run_in_background"],
        prompt=call["prompt"],
    )
    task_ids.append(task_id)
```

> **不要**自己写 `subagent_type="general-purpose"` 或 `run_in_background=true`——直接用 JSON 里的字段。
> **不要**在循环里调 TaskOutput——**循环外**统一等所有完成（这样后续 sub-agent 可以**继续后台跑**）。

#### 步骤 B.3：等所有 sub-agent 完成

```python
for task_id in task_ids:
    TaskOutput(task_id=task_id, block=true, timeout=600000)
```

#### 步骤 B.4：汇总结果

- 验证每个 `evidence/evolution_reports/<target_file_safe>.evolution_report.json` 是否生成
- 报告 N 成功 / M 失败 / 总 target_file 数
- 错误隔离：单个 target_file 失败不影响其他

输出汇总："批处理完成：N 成功 / M 失败 / target_files 总数 K"。

## 执行规则

- 只执行脚本，不输出额外解释
- 不询问用户确认
- 执行完成后停止
- 使用中文回答
- 模式判断严格按 $ARGUMENTS，**不要**从上下文/历史输出推断 target_file
