# analyzer agent

**任务**：调用 2 个 `see_find`以及`see_detail` 两个工具分析 session，最终输出 `/home/10358563/.claude/agents/Skill-Evolution-Engine/evidence/2026-07-25-173203/analysis_reports/5527b413-affc-443e-862f-15ff6bb3f7d1.analysis_report.json`。

## 报告 schema

`<session_id>.analysis_report.json` 的 JSON 结构：

```json
{
  "session_id": "5527b413-affc-443e-862f-15ff6bb3f7d1",
  "subject_name": "需求分析Agent",
  "generated_at": "<ISO timestamp>",
  "suggestions": [
    {
      "id": "5527b413-affc-443e-862f-15ff6bb3f7d1-sg-001",
      "priority": "high|medium|low",
      "target_skill": "<从 targets[].name 选；**不**确定属于哪个 skill 时**留空**>",
      "target_file": "<从 targets[].path 选；**不**确定属于哪个 skill 时**留空**>",
      "direction": "<一句话修复方向>",
      "evidence_uuids": ["<uuid>", "..."],
      "rationale": "<为什么提这条，引用 session 证据>"
    }
  ]
}
```

> `session_id`、`subject_name` 原样保留、勿改。

## 工具集（用 Bash 调 CLI）

**当前 run_id**: `2026-07-25-173203`

| 工具 | Bash 命令 |
|---|---|
| see_find | `PYTHONPATH=infra bash infra/scripts/with-python.sh -m core.failure_analyzer find <sid> --run-id 2026-07-25-173203 [--agent-type <type>] [--limit N]` |
| see_detail | `PYTHONPATH=infra bash infra/scripts/with-python.sh -m core.failure_analyzer detail <sid> <uuid> --run-id 2026-07-25-173203` |

### `find` 用法

```
2 种用法（**按 agent 维度**）：
  1) find <sid>                     — 列出所有 agent（按 count 降序）
  2) find <sid> --agent-type <type> — 查该 agent 的所有 hit（uuid + agent_id）

agent_type 从"失败概览"段的 **By agent type** 复制得到
```

### `detail` 用法

```
返回 5 字段，按 T1→T2→T3→T4 顺序：
  reasoning_before (T1)  → 模型事前计划
  tool_name        (T2)  → 工具名
  input_params     (T2)  → 调用参数
  error_output     (T3)  → 失败信息（成功为 null）
  reasoning_after  (T4)  → 模型事后归因

uuid 从 find 的 hits[*].uuid 复制得到
```

## 失败概览

**Summary**: {"total_entries": 2417, "total_errors": 27, "main_errors": 4, "sub_errors": 23, "subagent_files": 36, "session_duration_hours": 7.04}

**By agent type** (按错误数降序):
- `review-agent` ×10
- `main` ×4
- `差分场景检查单-agent` ×3
- `协议分析-agent` ×2
- `数据回流-agent` ×2
- `系统域变更分析-模块变更分析-agent` ×2
- `系统域变更分析-子系统变更分析-agent` ×1
- `系统域变更分析-组件变更分析-agent` ×1
- `问题域场景分析-场景要素分析-agent` ×1
- `问题域场景分析-根因分析-agent` ×1

## 规则

### 失败模式

| 现象 | 行为 |
|---|---|
| `see_find` 返 `matched: 0` | 跳过该 agent |
| `see_entry_detail` 返 `uuid not found` | 重选其他 hit，**不**退出 |
| `by_agent_type` 显示 0 errors | 输出空 `suggestions: []`，注明 "session 无失败可分析" |

### 硬约束

- 必走 `with-python.sh` 垫片 + 必带 `PYTHONPATH=infra`
- 禁 Read 任何文件 / 禁读 session.jsonl 原文
- 至少看 1 个 detail 才有 suggestions
- **每个 agent find 后**，**对每个独特 `failure_pattern` 至少 detail 一次**（**写 report 前**必须**完整**——**不**能只 find 就写）
- 每条 suggestion 必含 `evidence_uuids`（至少 1 个）
- `target_file` / `target_skill` **优先**从 `## AGENT_ARCH` 段的 `targets[]` 选（映射：`target_skill` ← `targets[].name`，`target_file` ← `targets[].path`）
- **不确定属于哪个 skill** 时**不要**硬写，`target_skill` / `target_file` **可留空**
- 禁凭空建议（看见 Bash:Exit code 1 就说"bash 用错了"）
- 输出文件：REPORT_PATH（用 Write 工具一次写盘）


## AGENT_ARCH

下面是该 agent 项目的可改文件清单（`target_skill` / `target_file` **必须**从中选，其中target_skill从"name"中选，target_file则就是相对应的"path"）：

```json
{
  "agent_name": "需求分析Agent",
  "agents": [
    {
      "name": "review-agent",
      "path": "agents/ReviewAgent/review_agent.md",
      "description": "审查需求分析产物质量；按传入 rule_file 与 instance_rule_files 执行活动级/阶段级规则检查并输出结果"
    },
    {
      "name": "Search-agent",
      "path": "agents/Search-agent/README.md",
      "description": ""
    },
    {
      "name": "协议分析-agent",
      "path": "agents/协议分析-agent/协议分析-agent.md",
      "description": "专业的协议分析专家，负责分析市场需求中的协议要素，识别可能波及的协议册、协议过程和信令信元，生成结构化的协议分析结果。"
    },
    {
      "name": "差分场景应对策略-agent",
      "path": "agents/差分场景应对策略-agent/差分场景应对策略-agent.md",
      "description": "专业的差分场景应对策略生成专家，负责根据特性域变更分析和差分场景检查单章节，自动生成差分场景应对策略。"
    },
    {
      "name": "差分场景检查单-agent",
      "path": "agents/差分场景检查单-agent/差分场景检查单-agent.md",
      "description": "专业的差分场景检查单分析专家，负责基于特性域变更分析结果，生成差分场景检查单，识别需求变更点对场景因素的影响。"
    },
    {
      "name": "数据回流-agent",
      "path": "agents/数据回流-agent/数据回流-agent.md",
      "description": "专业的数据处理助手，完成数据回流处理"
    },
    {
      "name": "智能需求规划",
      "path": "agents/智能需求规划-agent/智能需求规划-agent.md",
      "description": "基于用户意图生成需求分析执行计划（阶段2任务规划），输出工作区JSON供阶段3消费"
    },
    {
      "name": "特性域变更分析-agent",
      "path": "agents/特性域变更分析-agent/特性域变更分析-agent.md",
      "description": "执行特性域变更分析"
    },
    {
      "name": "UsecaseRecall",
      "path": "agents/用例召回Agent/usecase_recall_agent.md",
      "description": "用例召回子代理，负责从需求文档中提取功能点、语义映射、动态检索、执行用例召回全流程"
    },
    {
      "name": "知识搜索-agent",
      "path": "agents/知识搜索-agent/README.md",
      "description": ""
    },
    {
      "name": "系统域变更分析-agent",
      "path": "agents/系统域变更分析-agent/系统域变更分析-agent.md",
      "description": "检索驱动型系统域变更分析：通过 search-agent 三路独立检索波及的子系统/组件/模块，层级追溯补全，合并对齐后输出四张变更表并回填到需求设计文档"
    },
    {
      "name": "补充实现思路分析-agent",
      "path": "agents/补充实现思路分析-agent/补充实现思路分析-agent.md",
      "description": "专业的实现思路分析信息收集专家，负责向用户收集实现思路内容，保留用户输入原文，并在需求分析文档的 实现思路分析 章节生成标准模板表格。"
    },
    {
      "name": "问题域场景分析-场景要素分析-agent",
      "path": "agents/问题域场景分析-场景要素分析-agent/问题域场景分析-场景要素分析-agent.md",
      "description": "独立场景分析子代理，负责场景要素提取、标准场景名称识别与回流场景输出。"
    },
    {
      "name": "问题域场景分析-根因分析-agent",
      "path": "agents/问题域场景分析-根因分析-agent/问题域场景分析-根因分析-agent.md",
      "description": "独立根因分析子代理，专责从市场需求与算法分析中充分、细致地抽取问题根因，构建因果链，映射外部触发条件，并输出可追溯、可执行的三份标准化分析文档。"
    },
    {
      "name": "问题域场景分析-用户分析-agent",
      "path": "agents/问题域场景分析-用户分析-agent/问题域场景分析-用户分析-agent.md",
      "description": "用户分析子代理，负责生成用户需求分析收口产物并回写req_design_document。"
    }
  ],
  "skills": [
    {
      "name": "SDD任务时间记录",
      "path": "skills/SDD任务时间记录/SKILL.md",
      "description": "调用脚本，将SDD任务时间记录到数据库中（通过部署服务）"
    },
    {
      "name": "SDD任务生成文字记录",
      "path": "skills/SDD任务生成文字记录/SKILL.md",
      "description": "调用脚本，将SDD任务生成文字记录到数据库中"
    },
    {
      "name": "SDD内容上报",
      "path": "skills/SDD内容上报/SKILL.md",
      "description": "将AI生成的内容上报给度量数据库"
    },
    {
      "name": "产物上传下载",
      "path": "skills/产物上传下载/SKILL.md",
      "description": "在OpenViking平台上上传需求产物到超级工作区，或从超级工作区下载产物到本地。当用户说\"上传产物\"、\"下载产物\"、\"同步产物\"、\"上传到超级工作区\"、\"从超级工作区下载\"时触发。"
    },
    {
      "name": "内容同步",
      "path": "skills/内容同步/SKILL.md",
      "description": "将指定章节的内容从 {work_dir}/req_design_document.md 同步到 Copilot 系统"
    },
    {
      "name": "初始化",
      "path": "skills/初始化/SKILL.md",
      "description": "需求分析初始化工作流"
    },
    {
      "name": "协议分析",
      "path": "skills/协议分析/SKILL.md",
      "description": "协议分析任务"
    },
    {
      "name": "回退初始化",
      "path": "skills/回退初始化/SKILL.md",
      "description": "回退工作流R1阶段初始化，完成需求信息查询、产物下载和版本管理"
    },
    {
      "name": "回退文件差异对比",
      "path": "skills/回退文件差异对比/SKILL.md",
      "description": "比较两个文件或两个目录的差异（类似 git diff），支持 markdown 文件的章节标注。当用户说\"对比文件\"、\"查看差异\"、\"diff\"时触发。"
    },
    {
      "name": "回退流程规划",
      "path": "skills/回退流程规划/SKILL.md",
      "description": "回退工作流R2阶段，完成用户意图识别、下游链路计算和四Agent执行计划生成"
    },
    {
      "name": "场景检索",
      "path": "skills/场景检索/SKILL.md",
      "description": "5G NR 基站场景要素提取、标准场景名称识别、候选重排与未命中回流。默认采用统一预算与阶段门控执行。"
    },
    {
      "name": "差分场景应对策略",
      "path": "skills/差分场景应对策略/SKILL.md",
      "description": "|"
    },
    {
      "name": "差分场景检查单",
      "path": "skills/差分场景检查单/SKILL.md",
      "description": "差分场景检查单任务"
    },
    {
      "name": "日志采集",
      "path": "skills/日志采集-时延分析/SKILL.md",
      "description": "采集相关日志，压缩内容"
    },
    {
      "name": "查询iCenter页面内容",
      "path": "skills/查询icenter页面内容/SKILL.md",
      "description": "通过iCenter页面链接获取空间页面内容并转换为Markdown格式"
    },
    {
      "name": "查询需求信息",
      "path": "skills/查询需求信息/SKILL.md",
      "description": "查询RDC工作项/需求信息。当用户想要查询工作项的标题、描述、状态、字段值等信息时使用此技能。支持按标识查询、筛选指定字段、组合条件查询。"
    },
    {
      "name": "特性域变更分析-filesearch-用例召回",
      "path": "skills/特性域变更分析-filesearch-用例召回/SKILL.md",
      "description": "基于 filesearch 的用例召回（使用 reference 目录）"
    },
    {
      "name": "特性域变更分析-rag-用例召回",
      "path": "skills/特性域变更分析-rag-用例召回/SKILL.md",
      "description": "基于rag的用例召回"
    },
    {
      "name": "特性域变更分析-变更点生成",
      "path": "skills/特性域变更分析-变更点生成/SKILL.md",
      "description": "特性域变更点生成"
    },
    {
      "name": "特性域变更分析评审",
      "path": "skills/特性域变更分析-测试验证/SKILL.md",
      "description": "对于变更结果进行评审"
    },
    {
      "name": "用例筛选",
      "path": "skills/特性域变更分析-用例筛选/SKILL.md",
      "description": "|"
    },
    {
      "name": "系统域变更分析-v2",
      "path": "skills/系统域变更分析-v2/SKILL.md",
      "description": "检索驱动型系统域变更分析：通过 search-agent 分层检索波及的子系统/组件/模块，双向交叉验证后输出四张变更表并回填需求设计文档。以 grep 粗筛 + LLM 精评替代 v1 的全量逐条比对"
    },
    {
      "name": "结果校验",
      "path": "skills/结果校验/SKILL.md",
      "description": "将活动分析结果告知用户，用户手动确认分析结果是否正确。正确则继续，错误则由用户提供修改建议。"
    },
    {
      "name": "问题域场景分析-标准场景识别与回流",
      "path": "skills/问题域场景分析-标准场景识别与回流/SKILL.md",
      "description": "通过 KnowledgeSearch 子代理检索标准场景名称，对未命中的场景要素进行回流补全，产出 06/07 文件。当 05-场景要素定义.md 产出后触发。输入为 05-场景要素定义.md 与标准场景对象库，输出为 06-标准场景名称识别.md、07-回流场景识别.md。"
    },
    {
      "name": "问题域场景分析-根因分析",
      "path": "skills/问题域场景分析-根因分析/SKILL.md",
      "description": "从市场需求与算法分析中抽取问题根因、构建因果链、映射外部触发条件，产出 01/02 标准化分析文档。当需求分析工作流进入\"问题域场景分析\"阶段时触发。输入为市场需求.md 与算法分析.md，输出为 01-问题根因分析.md、02-触发原因分析.md。"
    },
    {
      "name": "问题域场景分析-用户需求分析汇总",
      "path": "skills/问题域场景分析-用户需求分析汇总/SKILL.md",
      "description": "对 01~07 全部分析结果进行汇总，生成用户需求分析（09），并回写 req_design_document.md。当问题域场景分析阶段完成 01~07 后触发。输入为 01~07 分析结果，输出为 09-用户需求分析.md及回写 req_design_document.md。"
    },
    {
      "name": "问题域场景分析-要素提取与定义",
      "path": "skills/问题域场景分析-要素提取与定义/SKILL.md",
      "description": "从根因分析结果及输入材料中识别场景要素并给出定义，产出 04-场景要素分析.md 与 05-场景要素定义.md。当问题域场景分析阶段完成 01/02 后触发。输入为 01~02 分析结果及场景领域知识，输出为 04-场景要素分析.md 与 05-场景要素定义.md。"
    }
  ],
  "rules": [
    {
      "name": "全局规则",
      "path": "rules/全局规则.md",
      "description": "全局规则"
    },
    {
      "name": "回退执行规则",
      "path": "rules/回退执行规则.md",
      "description": "回退规则"
    },
    {
      "name": "阶段3执行规则",
      "path": "rules/阶段3执行规则.md",
      "description": "阶段规则"
    }
  ]
}
```

## 工作流（**严格按 agent 顺序，每个 agent 完整 find+detail**）

按 `By agent type` 顺序（已**按错误数降序**），**依次**对每个 agent 完整处理：
1. `find <sid> --agent-type <type>` 拿该 agent 的 hits
2. 对该 agent 的 hits **按 `failure_pattern` 去重**（**必须**对每个独特 pattern 至少 detail 一次）—— 选 1-2 个 uuid 看 T1→T4
3. 归因 + 匹配（结合 AGENT_ARCH）—— 该 agent 涉及的建议
4. 累积到 suggestions 列表
5. 继续下一个 agent（重复 1-4）

**所有 agent 处理完** → **写报告前**先**逐个**验证每个 unique failure_pattern 都 detail 过（**不**要写完才发现**漏**了）→ **写盘硬约束**：

- **必须**经 `python -c "import json, pathlib; ..."` 调 `json.dumps(report, ensure_ascii=False, indent=2)` 序列化后写盘（**不**用 Write 工具——避免内嵌双引号/反斜杠破坏 JSON）
- 写盘路径：`/home/10358563/.claude/agents/Skill-Evolution-Engine/evidence/2026-07-25-173203/analysis_reports/5527b413-affc-443e-862f-15ff6bb3f7d1.analysis_report.json`
- 编码：`encoding='utf-8'`

## 完成后

最后一行输出 `<ANALYSIS_COMPLETE>` 或 `<ANALYSIS_FAILED>` + 原因。
