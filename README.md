# Skill Evolution Engine 使用说明

## 写在前面
**Python ≥ 3.8** 脚本走 `infra/scripts/with-python.sh` 垫片自动探测
**依赖**：`pip install pydantic`


## 阶段一：将原始 Claude Code session 数据切成轻量版，保留分析所需的 entry 级别证据，作为阶段二sub-agent的证据源

执行脚本：
```bash
PYTHONPATH=infra bash infra/scripts/with-python.sh infra/scripts/see-collect.py [<projects_dir> <projects_simplified_dir>]
```
**注意：**
其中projects_dir与projects_simplified_dir分别为原始session数据的文件路径以及输出的文件路径
projects_dir的默认值为evidence/projects
projects_simplified_dir默认值为evidence/< run-id >/projects-simplified

其中`run_id` 是see-collect.py脚本执行的时间戳（`YYYY-MM-DD-HHMMSS`）


## 阶段二：从精简数据中识别失败模式，生成结构化分析报告，给出指向具体 skill 文件的改进建议（suggestions）
执行脚本：
```bash
PYTHONPATH=infra bash infra/scripts/with-python.sh infra/scripts/see-analyze.py <session_id> --run-id <id> [--output <prompt.md>]
```
see-analyze.py的入参：session_id与run-id 都是阶段一脚本的执行产物
默认的输出文件夹为evidence/< run-id >/analysis_reports
该脚本会首先执行see_failure_overview，在projects-simplified文件夹下生成.index的索引文件

**注意：**
需要确保.index产物的agent_cwd字段，如"/media/vdc/V3Bak/SDD/prcoess/workspace/需求分析Agent"
脚本通过“需求分析Agent”来从agent-architectures文件夹下找到该session所执行的工作流架构信息

## 阶段三：根据 suggestions 自动重写目标 skill 文件，输出完整升级版到 `.change` 文件
首先执行脚本，列出待进化的文件，依靠 (subject_name, target_file)定位
```bash
    PYTHONPATH=infra bash infra/scripts/with-python.sh infra/scripts/evolve-discovery.py --run-id <id>
```

输出：
```json
   {
     "targets": [
       {"subject_name": "...", "target_file": "..."}, 
       ...
     ]
   }
```

接下来将evolve-discovery.py的输出一次作为see-evolve.py的入参
```bash
PYTHONPATH=infra bash infra/scripts/with-python.sh infra/scripts/see-evolve.py <subject_name> <target_file> --run-id <id>
```

最终产物放在evidence/< run-id >/evolution_changes文件夹下
**注意：**
需要确保subjects文件夹下配置了相应的待进化文件
因为see-evolve.py脚本给进化sub-agent的提示词就是根据"根目录的绝对路径/subjects/<subject_name>/ <target_file> "拼出来的，agent会从这个绝对路径中找原始SKILL.md


## 快速启动（3 个 command 命令）

工作目录必须始终是 **Skill-Evolution-Engine 项目根**

### 阶段 1 · 数据采集

```bash
/see-collect
```

或显式指定输入（不建议指定输出）：

```bash
/see-collect evidence/projects
```

> 跑完从 stdout 复制 `run_id` 和 `session_ids[]` —— 后续两阶段都靠这个 `run_id` 串联。

### 阶段 2 · 失败分析（默认批处理）

```bash
/see-analyze                    # 批处理：自动用阶段 1 的 session_ids
/see-analyze <session_id>       # 单 session：只分析一个
```

阶段 2 由主 agent **并行**起 N 个 analyzer sub-agent（`subagent_type=general-purpose`、`run_in_background=true`），各自把报告写到 `evidence/<run_id>/analysis_reports/<sid>.analysis_report.json`。

### 阶段 3 · Skill 进化（默认批处理）

```bash
/see-evolve                                       # 批处理：先 discovery 再逐个 fire evolver
/see-evolve <subject_name> <target_file>           # 单 target：只进化一项
```

阶段 3 把升级后的完整文件写到 `evidence/<run_id>/evolution_changes/<subject_name>__<flatten_target_file>.change`，**不会动**原文件。

阶段2与阶段3的 `.py` 脚本的 stdout 都是一段 JSON（4 字段 Agent 调用配置），主 agent 拿这段 JSON 去 `Agent(subagent_type=…, run_in_background=true, prompt=…)` 调用sub-agent进行工作

## 快速启动（自然语言描述）
1.若将要处理的session放到了Skill-Evolution-Engine/evidence/projects文件夹下，则可以不指定session路径，直接输入：
帮我执行这个工作流

2.指定session所存储的位置
帮我执行这个工作流，session存储的位置在：（此处写入绝对路径）

## 输出目录契约（一次 `run_id` 的全貌）

```text
evidence/<run_id>/
├── projects-simplified/                          # 阶段 1 产物
│   ├── <sid>.jsonl
│   └── <sid>/subagents/
│       ├── agent-*.jsonl
│       └── agent-*.meta.json
├── analysis_reports/                             # 阶段 2 产物
│   └── <sid>.analysis_report.json
└── evolution_changes/                            # 阶段 3 产物
    └── <subject_name>__<flatten_target_file>.change
```

- `<run_id>` = `YYYY-MM-DD-HHMMSS`
- `<flatten_target_file>` = 把 `/` 替换成 `__` 后的相对路径，例如 `skills/查询需求信息/SKILL.md` → `skills__查询需求信息__SKILL.md`
- **不要手改**上述目录下的文件——脚本下次启动会按"完成标志"判定阶段是否已跑

## 相关文档

- [CLAUDE.md](CLAUDE.md) — 主 agent 行为约定（中文） + 项目结构
- [rules/main-agent-rules.md](rules/main-agent-rules.md) — 主 agent 调度规则
- [rules/analyzer-agent-rules.md](rules/analyzer-agent-rules.md) — analyzer sub-agent 规则
- [rules/evolver-agent-rules.md](rules/evolver-agent-rules.md) — evolver sub-agent 规则
- [infra/phases/phase1-collect.md](infra/phases/phase1-collect.md) — 阶段 1 详细流程
- [infra/phases/phase2-analyze.md](infra/phases/phase2-analyze.md) — 阶段 2 详细流程
- [infra/phases/phase3-evolve.md](infra/phases/phase3-evolve.md) — 阶段 3 详细流程
