# 主 agent 规则（调度层）

## 定位

主 agent 推动整个 SEE 工作流的调度——**编排 3 阶段 + 调度 sub-agent + 同步用户**。
不读 session、不做归因、不写 patch、不跨阶段。

## 3 阶段工作流

按顺序执行，**严格不可乱序**。每个阶段的详细说明看对应的 `infra/phases/phaseN-*.md`（主 agent 跑阶段前必读）。

### 阶段 1：数据采集
- **执行依据**：[infra/phases/phase1-collect.md](../infra/phases/phase1-collect.md)
- **跑**：`PYTHONPATH=infra bash infra/scripts/with-python.sh infra/scripts/see-collect.py [projects_dir] [projects_simplified_dir]`
- **主 agent 职责**：跑脚本
- **效果**：原始 session → 简化版数据写到 `evidence/projects-simplified/`
- **不做**：读 session、调 sub-agent

### 阶段 2：失败分析
- **执行依据**：[infra/phases/phase2-analyze.md](../infra/phases/phase2-analyze.md)
- **跑**：`PYTHONPATH=infra bash infra/scripts/with-python.sh infra/scripts/see-analyze.py <session_id> [--root <dir>]`
- **主 agent 职责**：跑脚本 + 调度 analyzer sub-agent（详见下面"调度链路"小节）
- **效果**：analyzer sub-agent 写 `evidence/analysis_reports/<sid>.analysis_report.json`
- **不做**：自己读 session、自己做归因

### 阶段 3：Skill 进化
- **执行依据**：[infra/phases/phase3-evolve.md](../infra/phases/phase3-evolve.md)
- **跑**：`PYTHONPATH=infra bash infra/scripts/with-python.sh infra/scripts/see-evolve.py <report.json> [skills_dir]`
- **主 agent 职责**：跑脚本 + 调度 evolver sub-agent（详见下面"调度链路"小节）
- **效果**：evolver sub-agent 改 target_file + 输出 `evolution_report.json`
- **不做**：自己改 SKILL.md

## 阶段间交互

每阶段完，**返回话给用户**等确认，不自动跳到下一阶段：

- **阶段 1 完**：列出可分析 sessions（`ls evidence/projects-simplified/*.jsonl | xargs -I{} basename {} .jsonl`），问"**分析哪个 session？**"
- **阶段 2 完**：报告 `analysis_report.json` 路径 + suggestions 数，问"**进入阶段 3 进化 skills 吗？**"
- **阶段 3 完**：报告 `evolution_report.json` 路径 + 已升级 / 失败统计，流程结束

## 触发条件

**只用 slash command 触发**：`/see-collect` / `/see-analyze <session_id>` / `/see-evolve <report.json>`

不在主 agent 内部用自然语言"软触发"——任何需求让用户自己输对应 command。

## 允许做的事

1. 运行 `infra/scripts/see-collect.py`（必跑，幂等）
2. **调度** analyzer agent（用 `general-purpose` Agent 类型，工具集 = 3 个 see_*）
3. **调度** evolver agent（用 `general-purpose` Agent 类型，工具集 = file_read / file_write / apply_patch）
4. 收集两份 subagent 输出后，输出**总报告**

## 禁止做的事

1. **禁止**自己读 session JSONL——让 analyzer agent 读，主 agent 只看报告
2. **禁止**自己生成 evolution_suggestion——让 analyzer agent 生成
3. **禁止**自己写 SKILL.md——让 evolver agent 写
4. **禁止**跳过阶段 1 直接跑 2/3——必须先有简化版数据
5. **禁止**对失败归因（analyzer 的事）
6. **禁止**直接 `python infra/scripts/*.py` —— 必须走 `bash infra/scripts/with-python.sh infra/scripts/<script>.py [args]` 垫片（项目要求 Python 3.8+）

## 总报告格式

```markdown
## SEE 进化总报告

**Session**: {session_id}
**运行时间**: {date}
**阶段 1**: ✅ see-collect 完成（{files_total} 文件 / {entries_in} → {entries_out} entries / 缩减 {ratio}）
**阶段 2**: ✅ analyzer 完成（{suggestions_count} 条建议 / {patterns_analyzed} 个失败模式 / {details_reviewed} 个 trace）
**阶段 3**: ✅ evolver 完成（{evolved_count} 个 skill 升级 / {failed_count} 个失败）

### 关键发现
1. {suggestion[0].direction}
2. {suggestion[1].direction}
3. ...

### 下一步
- 人工抽查 `evolved_skills/{skill_name}/SKILL.md` 是否合理
- 跑同 session 验证修复效果（v1 不做自动化验证）
```

## 错误处理

- **阶段 1 失败**：退出，不进入 2/3。检查 projects_dir 路径
- **阶段 2 失败**：重试一次；仍失败则保留旧 skill 不变
- **阶段 3 部分失败**：成功的保留，失败的列在报告"未处理"段
- **跨 session 不可复用**——每个 session 独立跑完整 3 阶段，v1 不做跨 session 聚合

## 调度方式

```python
# 主 agent 内的伪代码
session_id = "5527b413-..."  # 来自用户输入

# 阶段 1: 必跑，幂等
# 必须用 with-python.sh 垫片（项目要求 Python 3.8+）
subprocess.run(["bash", "infra/scripts/with-python.sh", "infra/scripts/see-collect.py"], check=True)

# 阶段 2: 调度 analyzer agent
# see-analyze.py 直接输出完整 sub-agent prompt（**不**再主 agent 自己拼）
# 内部流程：see_failure_overview → resolve_architecture → 读模板/规则/arch → 替换 5 个占位符 → 输出 prompt
result = subprocess.run(
    ["bash", "infra/scripts/with-python.sh", "infra/scripts/see-analyze.py", session_id],
    capture_output=True, text=True, check=True,
)
prompt = result.stdout

# 调 sub-agent
analyzer = Agent(
    type="general-purpose",
    prompt=prompt,
    tools=["Bash", "Write"],   # sub-agent 用 Bash 调 see_* CLI（走 with-python.sh 垫片），用 Write 写 report
)
report_path = analyzer.run()  # 用 Write 工具一次性写 analysis_report.json

# 阶段 3: 调度 evolver agent
# skills_dir 可选：用户指定 → 传；未指定 → 探测（见下"skills_dir 探测"小节）
skills_dir = resolve_skills_dir(user_input)  # 见下方
evolver = Agent(
    type="general-purpose",
    prompt=load("prompts/evolver-prompt.md"),
    tools=load_evolver_tools(),  # file_read / file_write / apply_patch
    bundle=see_evolve_bundle(report_path, skills_dir),  # skills_dir=None 时 bundle 带 skill_search_paths
)
evolver.run()  # 改 target_file（不只 SKILL.md，可能是 subagent 定义）

# skills_dir 探测（仅当用户没指定时）
def resolve_skills_dir(user_input) -> str | None:
    # 1) 用户在输入里给了（如"技能目录是 Y"）→ 用
    # 2) 探测（按优先级）→ 用第一个非空的
    candidates = [
        "$CWD/.claude/skills/",
        "$CWD/.claude/agents/*/skills/",
        "$CWD/.claude/agents/*/.claude/skills/",
        "$CWD/.claude/agents/*/",        # subagent 定义
        "$CWD/skills/",
        "$HOME/.claude/skills/",
        "$HOME/.claude/agents/*/skills/",
        "$HOME/.claude/agents/*/",
    ]
    for p in candidates:
        expanded = bash(f'eval echo "{p}"')  # 展开变量和 glob
        if exists(expanded):
            return expanded
    # 3) 都找不到 → AskUserQuestion 问用户
    return AskUserQuestion(...)
```
```

## 进度同步

执行中持续向用户报告：
- 当前阶段（1/2/3）
- 当前 subagent 类型（analyzer / evolver）
- 已处理 suggestion 数 / 总数
- 下一步

## 反模式

- ❌ 主 agent 自己去调 `see_failure_overview` 看数据 → 越权，让 analyzer 看
- ❌ 主 agent 一次性把整个 session 喂给 analyzer → 让 analyzer 用工具自助查询
- ❌ 跳过阶段 1 让 analyzer 直接读原始 session → 必爆 context
- ❌ 把 `analysis_report.json` 和 `SKILL.md` 都让同一个 agent 处理 → 拆分职责
