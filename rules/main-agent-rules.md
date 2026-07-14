# 主 agent 规则（调度层）

## 定位

主 agent 推动整个 SEE 工作流的调度——**编排 3 阶段 + 调度 sub-agent + 同步用户**。
不读 session、不做归因、不写 patch、不跨阶段。

## 3 阶段工作流

按顺序执行，**严格不可乱序**。每个阶段的详细说明看对应的 `infra/phases/phaseN-*.md`（主 agent 跑阶段前必读）。

### 阶段 1：数据采集
- **执行依据**：[infra/phases/phase1-collect.md](../infra/phases/phase1-collect.md)
- **主 agent 职责**：执行`PYTHONPATH=infra bash infra/scripts/with-python.sh infra/scripts/see-collect.py [projects_dir] [projects_simplified_dir]`脚本
- **效果**：原始 session → 简化版数据写到 `evidence/projects-simplified/`

### 阶段 2：失败分析
- **执行依据**：[infra/phases/phase2-analyze.md](../infra/phases/phase2-analyze.md)
- **主 agent 职责**：根据**是否含 session_id** 走两种执行模式：
  - **单 session 模式**：执行 `PYTHONPATH=infra bash infra/scripts/with-python.sh infra/scripts/see-analyze.py <session_id> [--root <dir>]` 一次 + 调一次 analyzer sub-agent
  - **批处理模式**（默认，无 session_id）：从阶段 1 stdout 解析 `session_ids[]`，**并行**对每个 sid 执行 `see-analyze.py <sid>` + 调 analyzer sub-agent（fan-out，sub-agent 后台运行）
- **效果**：analyzer agent 生成 `evidence/analysis_reports/<session_id>.analysis_report.json`（每个 sid 一份）

### 阶段 3：Skill 进化
- **执行依据**：[infra/phases/phase3-evolve.md](../infra/phases/phase3-evolve.md)
- **主 agent 职责**：先跑 `evolve-discovery.py` 拿 `targets[]`（每项 = `{subject_name, target_file}`），再**逐个** target 跑 `see-evolve.py <subject_name> <target_file>` 拿 4 字段 JSON + 用该 JSON 原样调度 evolver sub-agent（`run_in_background=true` 后台并发）
- **效果**：evolver agent 把升级后的**完整文件**写到 `evidence/evolution_changes/<flatten>.change`（**不改**原文件）

## 阶段间交互

每阶段完，**返回话给用户**等确认，不自动跳到下一阶段：

- **阶段 1 完**：从 stdout 解析 `session_ids[]`（取代 glob 列出 sessions），问"**分析哪个 session（或全部分析）？**"
- **阶段 2 完**：报告 `analysis_report.json` 路径 + suggestions 数，问"**进入阶段 3 进化 skills 吗？**"
- **阶段 3 完**：报告已生成的 `.change` 文件列表 + 已升级 / 失败统计，流程结束

## 触发条件

主 agent **同时**支持两种触发：

- **Slash command**（直接调用）：
  - `/see-collect [projects_dir] [simplified_dir]`
  - `/see-analyze <session_id> [--root <dir>]`（单 session 模式）
  - `/see-analyze`（无参数 → 批处理模式，阶段 1 stdout 的 `session_ids` 自动作为任务）
  - `/see-evolve [subject_name target_file]`（含 subject_name + target_file → 单 target 模式；无参数 → 批处理，先 discovery 再逐个 fire）
- **自然语言**（智能判断阶段 + 兜底补做之前阶段）：
  - 用户说 "采集 session X" / "处理 X" / "收集 X" → 阶段 1
  - 用户说 "分析 X" / "帮我分析 sid" / "处理 sid 失败" → 阶段 2 单 session 模式
  - 用户说 "分析所有" / "批处理" / "跑阶段 2 batch" / 不带 sid 的 "分析" → 阶段 2 **批处理模式**
  - 用户说 "进化 X" / "升级 skill" / "改造 X" → 阶段 3
  - 例外：`/see-collect` / `/see-analyze` / `/see-evolve` 命令**也**保留（直接用时**不**触发阶段判断）

### 阶段完成标志

主 agent **自动**判断**之前阶段是否完成**（根据文件存在）：

- 阶段 1 完成 = `evidence/projects-simplified/<session_id>.jsonl` 存在
- 阶段 2 完成 = `evidence/analysis_reports/<session_id>.analysis_report.json` 存在
- 阶段 3 完成 = `evidence/evolution_changes/<subject_name>__<flatten_target_file>.change` 存在（每对 subject/target 一份）

### 自然语言触发流程

当用户用自然语言触发（不是 slash command）：

1. **判断要进哪阶段 + 执行模式**（**从**用户消息提取 session_id / keywords）
   - "采集" / "处理" / "收集" → 阶段 1
   - "分析 sid" / "失败" → 阶段 2 单 session 模式
   - "分析所有" / "批处理" / "跑阶段 2 batch" / 不带 sid 的 "分析" → 阶段 2 **批处理模式**
   - "进化" / "升级" → 阶段 3
2. **检查**之前阶段是否完成（按上表标志）
3. **如**之前阶段**未**完成 → **先**补做（**不**跳过）
   - 例：用户说"分析 sid"但 `projects-simplified/<sid>.jsonl` **不**在 → **先**跑阶段 1，**再**跑阶段 2
4. **如**之前阶段已完成 → 跳过，**直接**跑当前阶段
5. 跑完后报告结果 + 问用户"进下一阶段吗"

## 进度同步

每阶段完**报告** + **问**用户下一步：

- **阶段 1 完**：
  - 报告"原始 session → 简化版数据已写到 `evidence/projects-simplified/`"
  - 解析 stdout 的 `session_ids[]`，问"**分析哪个 session（或全部分析）？**"
- **阶段 2 完**：
  - 报告 `analysis_report.json` 路径 + suggestions 数（`jq '.suggestions | length'`）
  - 问"**进入阶段 3 进化 skills 吗？**"
- **阶段 3 完**：
  - 报告已生成的 `evidence/evolution_changes/*.change` 文件列表 + 已升级 / 失败统计
  - 流程结束

执行中**实时**报告：
- 当前阶段（1/2/3）
- 当前 subagent 类型（analyzer / evolver）
- 已处理 suggestion 数 / 总数
- 下一步动作