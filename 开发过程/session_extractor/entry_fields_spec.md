# Session Entry 字段保留规范 (v4)

## 目标

精简 Claude Code session JSONL，**目的**是让下游 LLM **找到"需求分析 agent"在执行中暴露的问题**（skill 执行逻辑、agents 配置、prompt、工作流），进而**进化该 agent**。

**v4 与 v3 关键差异**（用户 2026-06-27 拍板）：

1. **truncate_enabled 默认 true**（v3 默认 false）。`_META._TRUNCATE` 规则生效：超长 stdout / stderr / content / text 头部 2KB + 尾部 1KB（text 头部 6KB）。`is_error=true` 整段保留。
2. **新增 detector 层**（5 类）：`state_machine` / `gate` / `review_contract` / `user_confirmation` / `symlink`。详见 §11。
3. **新增 agent_spec YAML**（`specs/`）：detector 由 spec 驱动，spec 缺省时走默认规则。详见 §11.5。
4. **v3 副作用删除**：主脚本不再写回 `entry_fields_config.json`。新增 `--write-config-defaults` 显式一次性写回。
5. **删除 v3 的 attachment 整类型 DROP 行为**（除 queue-operation / file-history-snapshot / last-prompt / system / permission-mode 外）：v4 保留 attachment 子类型细化（attachment.{hook_success / todo_reminder / skill_listing}）由 detector 层路由。
6. （v4 早期新增 `_META._EXPANDABLE_PATHS`：**已删除** — 代码无人读，仅是历史遗留的"文档注释"。详见 §11.7）。
7. **第 1 行 header 同时含 v3 兼容键与 v4 扩展键**：`schema_version=4.0` / `state_machine` / `constraint_events` / `user_feedback` / `execution_pattern` / `detector_meta`。第 2+ 行 NDJSON trace 字段集与 v3 完全一致。
8. **CLI 增强**：`--no-detectors` / `--detector X` / `--spec-dir Y` / `--truncate` / `--no-truncate` / `--write-config-defaults` / `--quiet`。
9. **分类细化**：`classifier` 仍返回 `"attachment"` 字面量；pipeline 在 classify 后把 attachment 细化为 `"attachment.{subtype}"`（与 simplifier 内部行为一致）。
10. **黑名单模式（drop only）**：v4 删除了 v3 的 `required` / `recommended` / `optional` 三层字段定义 — 实测三层实现完全相同（"有就保留，没有就跳过"），多此一举。v4 改为**纯黑名单**：每个 entry_class 仅声明 `drop` 列表，其他字段**默认保留**。好处：(1) 配置量减半；(2) Claude Code 新增字段自动透传，detector 可灵活读取；(3) 黑名单更易维护。**tradeoff**：必须显式列出要 drop 的字段（包括 `type`），漏列则字段残留。

**v3 与 v2 关键差异**（用户 2026-06-26 拍板）：
1. **整类型 DROP 5 个**：`queue-operation` / `file-history-snapshot` / `last-prompt` / `system` / `permission-mode`（即不进入 config，classifier 标 entry_class 后 simplifier 直接丢弃整条）。
2. **attachment 仅保留 `hook_success`**；`todo_reminder` 与 `skill_listing` 整类型 DROP。
3. **不保留** `message.model` / `message.usage` / `message.content[*].type`。
4. **保留** `message.stop_sequence`（用户偏保守）。
5. **truncation 默认关闭**（可由 CLI `--truncate` 或 config `truncate_enabled: true` 开启）。
6. **session 共享字段上提**：`sessionId` / `version` / `entrypoint` / `isSidechain` / `userType` / `cwd` 6 个字段由 `session_simplifier.py` 写到输出文件第 1 行的 session header，不在单条 entry 内出现。
7. **cwd 跳变插 `cwd_change` entry**：`session_simplifier.py` 主流程扫描时若发现 cwd 变化，自动插入特殊 entry。
8. **字段扁平化不做**：保留 `message` 包裹层（实现复杂度权衡）。

**v3.1 增量差异**（用户 2026-06-26 进一步拍板）：
9. **全局删除 `type` 字段**：顶层 `type` 与 `message.content[*].type` 都删除。下游靠 `entry_class` 识别类型。
10. **user_command 保留 `message`**：用户认为 `<local-command-caveat>` 等系统命令的具体内容对"找问题"也重要（保留 caveat 全文以供后续追溯）。

---

## 输出文件结构

```
{"session": {"sessionId":"…","version":"…","entrypoint":"…","isSidechain":false,"userType":"…","cwd":"…"}, "cwdChanges":0}
{"type":"user_input", "uuid":"…", …}
{"type":"ai_text", …}
{"type":"tool_result", …}
{"type":"cwd_change", "uuid":"…", "timestamp":"…", "cwd":"/new", "prevCwd":"/old"}   # 自动插入
{"type":"ai_tool_call", …}
{"type":"attachment.hook_success", …}
…
```

第 1 行 = session header + cwdChanges 计数。
后续行 = NDJSON entries（含可能自动插入的 `cwd_change`）。

---

## 字段保留原则（v4 黑名单模式）

1. **默认保留**：所有 entry 原字段默认透传到输出。
2. **drop 列表显式删除**：每个 entry_class 配置块仅声明 `drop` 列表，列出要删除的字段。
3. **整类型 DROP**：`entry_class` 不在 config 顶层 key 中 → 整条丢。
4. **`entry_class` 强制保留**：即使原 entry 没有 `entry_class` 字段，simplifier 也会强制写入（attachment 还会细化为 `attachment.{subtype}`）。

**v3.1 跨类型规则**：
- **`type` 字段全局删除**：顶层 `type` 和 `message.content[*].type` 都不进入输出。下游靠 `entry_class` 区分类型。
- 任何"需要 type 区分的子类型"应通过 entry_class 后缀表达（如 `attachment.hook_success`）。

---

## 1. 整类型 DROP（不进入 config，simplifier 见到即整条丢）

| entry_class | 原因 |
|---|---|
| `queue-operation` | 队列 enqueue/dequeue 节奏信息，无 agent 行为信号 |
| `file-history-snapshot` | 文件版本管理记账，无分析价值 |
| `last-prompt` | 与 user_input 重复，user_input 已覆盖 |
| `system` | hook 总结等系统内部事件，hook 信息已在 attachment.hook_success |
| `permission-mode` | 权限模式变更罕见且可从 cwd_change 时序旁路推断 |

---

## 2. attachment 整类型 DROP

| attachment subtype | 原因 |
|---|---|
| `attachment.todo_reminder` | 渲染 todo 列表，与 user_input / ai_text 内容重叠 |
| `attachment.skill_listing` | skill 列表快照，发现性问题可从 ai_tool_call 倒推 |

**仅保留** `attachment.hook_success` —— hook 配置与执行时延对"找问题"是高价值信号。

---

## 3. `user_command`（保留 message，丢掉其他元信息）

`<local-command-caveat>` 等系统注入命令。v3.1 改为**保留 `message.content`**（用户认为 caveat 命令内容对"找问题"也重要），其他环境元信息仍 DROP。

### 必留
- `uuid, parentUuid, timestamp, message, entry_class`

### 不留
- `promptId` / `sessionId` / `permissionMode` / `entrypoint` / `isSidechain` / `userType` / `cwd` / `version` / `gitBranch` / `isMeta`

---

## 4. `user_input`（用户真实输入）

### 必留
- `uuid, parentUuid, timestamp, type, entry_class`
- `message.content`（text 字符串 或 `list[{text}]`）

### 建议保留
- `promptId`（同轮多 entry 分组）

### 可选保留
- `permissionMode`（mid-session 权限变化罕见但有信号）

### 不留
- `entrypoint, isSidechain, userType, cwd, version, gitBranch, isMeta, agentId`

---

## 5. `tool_result`（工具执行结果）

### 必留
- `uuid, parentUuid, timestamp, type, entry_class`
- `message.content[*].tool_use_id`（与 ai_tool_call 配对）
- `message.content[*].is_error`（工具成败信号）
- `sourceToolAssistantUUID`（UUID 级关联）

### 建议保留
- `toolUseResult`（AI 视角的结构化执行结果）
- `message.content[*].content`（in-band 内容，与 toolUseResult 互补 —— Bash 字节全等，Read 摘要，Edit 状态句）

### 可选保留
- `promptId`

### 不留
- `message.content[*].type`（有 `entry_class` 路由就够区分，type 冗余）
- `isSidechain, userType, cwd, version, gitBranch, entrypoint, isMeta`

---

## 6. `ai_text`（assistant 文本输出）

### 必留
- `uuid, parentUuid, timestamp, type, entry_class`
- `message.content[*].text`（含 <think>）
- `message.stop_reason`（end_turn / tool_use）
- `message.stop_sequence`（用户偏保守保留）

### 建议保留
- `message.id`（provider 消息 id）

### 不留
- `message.content[*].type`（冗余）
- `message.model` / `message.usage`（v3 删除）
- `isSidechain, userType, cwd, version, gitBranch, entrypoint`

---

## 7. `ai_tool_call`（assistant 工具调用）

### 必留
- `uuid, parentUuid, timestamp, type, entry_class`
- `message.content[*].id`（与 tool_result 配对）
- `message.content[*].name`（工具名：Bash/Read/Edit/Skill/Agent/Write）
- `message.content[*].input`（工具参数）
- `message.stop_reason`
- `message.stop_sequence`

### 建议保留
- `message.id`

### 不留
- `message.content[*].type`（冗余）
- `message.model` / `message.usage`（v3 删除）
- `isSidechain, userType, cwd, version, gitBranch, entrypoint`

---

## 8. `attachment.hook_success`（唯一保留的 attachment subtype）

### 必留
- `uuid, parentUuid, timestamp, type, entry_class`
- `attachment.type`（判别）
- `attachment.hookName`（哪个 hook）
- `attachment.hookEvent`（触发时机：PreToolUse/PostToolUse/Stop）
- `attachment.command`（hook 执行命令）
- `attachment.exitCode`（成败）
- `attachment.durationMs`（时延性能）

### 建议保留
- `attachment.stdout, attachment.stderr`（按 `_TRUNCATE` 截断，启用时）

### 不留
- `attachment.content`（结构化字段已覆盖）
- `isSidechain, userType, cwd, version, gitBranch, entrypoint`

---

## 9. `ai-title`（自动会话标题）

### 必留
- `type, aiTitle, entry_class, timestamp`

### 不留
- `sessionId`（已在 session header）

---

## 10. `cwd_change`（v3 自动插入的特殊 entry）

`session_simplifier.py` 主流程扫描时发现 cwd 变化即生成。`entry_class == "cwd_change"`。

### 必留
- `type, entry_class, uuid, timestamp, cwd, prevCwd`

---

## 跨切面规则

### `_META._TRUNCATE`（仅 `truncate_enabled: true` 时生效）

| 路径 | 规则 |
|---|---|
| `toolUseResult.stdout` | head 2KB + tail 1KB；is_error=true 整段保留 |
| `toolUseResult.stderr` | 同上 |
| `message.content[*].content` | head 2KB + tail 1KB；is_error=true 整段保留；空值写 `"(empty)"` |
| `message.content[*].text` | head 6KB + tail 1KB |
| `attachment.stdout` / `attachment.stderr` | head 2KB + tail 1KB；is_error=true 整段保留 |

**默认关闭** —— 不设置时所有 body 完整保留。CLI `--truncate` 或 config `truncate_enabled: true` 启用。

---

## Session Header（第 1 行）

```json
{"session": {"sessionId": "...", "version": "...", "entrypoint": "...", "isSidechain": false, "userType": "...", "cwd": "..."}, "cwdChanges": N}
```

- 从原 session 第一条带这些字段的 entry 提取
- `cwdChanges` = 本 session 内 cwd 跳变次数（用于下游快速判断）
- 下游 LLM 读第 1 行 → 拿元信息；读 2+ 行 → 顺序遍历 entries（含可能插入的 cwd_change）

---

## cwd_change entry 协议

```json
{
  "type": "cwd_change",
  "entry_class": "cwd_change",
  "uuid": "<newly-generated>",
  "timestamp": "<当前扫描 entry 的时间戳>",
  "prevCwd": "/old/cwd",
  "cwd": "/new/cwd"
}
```

**插入位置**：在主流程扫描到 cwd 跳变的 entry 之前/之后？由 `session_simplifier.py` 决定（推荐：紧跟跳变后的 entry 之后插入，时间戳对齐）。

**判别规则**：相邻 entry 的 `cwd` 字段值不同即视为跳变。

**验证数据**（2026-06-26 已扫）：153/167 测试 sessions single cwd，12/167 multi cwd（agent 跳子目录）。

---

## 总结

### 高价值 entry_class
1. `user_input` —— 用户需求与期望
2. `ai_text` —— agent 推理与决策
3. `ai_tool_call` —— 工具调用模式
4. `tool_result` —— 工具成败与输出
5. `attachment.hook_success` —— hook 配置与时延

### 整类型 DROP
6. `user_command`（系统注入警告）
7. `attachment.todo_reminder`
8. `attachment.skill_listing`
9. `queue-operation`
10. `file-history-snapshot`
11. `last-prompt`
12. `system`
13. `permission-mode`

### 特殊 entry
14. `cwd_change`（v3 自动插入）
15. `ai-title`（会话主题索引）

### 进化建议来源
1. **用户反馈**：`user_input.message.content`
2. **AI 决策**：`ai_text.message.content[*].text`（含 <think>）
3. **工具使用**：`ai_tool_call.message.content[*].name + input`
4. **执行结果**：`tool_result` 的 `is_error` 与 `toolUseResult`
5. **性能数据**：`attachment.hook_success.durationMs`
6. **cwd 行为**：`cwd_change` entry 反映 agent 跳目录模式
7. **会话主题**：`ai-title`

---

## §11 v4 detector 协议

v4 collector 在分类 + 精简之后，跑 5 个 detector 产出**硬约束事件流**，写到 header 的扩展字段：

```json
{
  "schema_version": "4.0",
  "session": {...},
  "cwd_changes": N,
  "trace": [...],
  "state_machine": {
    "phases": ["phase0", "phase2", "phase4"],
    "transitions": [{"phase":"phase0","hook_event":"PreToolUse","role":"pre-init workdir","trigger_attachment_command":"phase0 pre-init workdir","trigger_entry_uuid":"...","trigger_hook_name":"PreToolUse:Skill","at":"..."}],
    "unexpected_exits": []
  },
  "constraint_events": [
    {"kind":"gate_rejected","gate_script":"phase0-pre-init-workdir","phase":"phase0","exit_code":2,"stop_reason":"无法提取需求ID","evidence_ref":"uuid","at":"...","retry_seen_after":true},
    {"kind":"review_contract","issue":"missing_required_field","reviewer_subagent_type":"review-agent","expected_subagent_types":["review-agent"],"actual_subagent_type":"review-agent","retry_count":2,"evidence_ref":"uuid","at":"..."}
  ],
  "user_feedback": [{"uuid":"...","text":"...","timestamp":"..."}],
  "execution_pattern": {
    "step_counts": {"user_input":4, "ai_text":16, "ai_tool_call":17, "tool_result":17, "attachment.hook_success":18},
    "retry_loops": [],
    "tool_distribution": {"Read":9, "Bash":4, "Edit":1, "Skill":1, "Agent":1},
    "phase_durations": {"phase0": {"start":"...","end":"..."}}
  },
  "detector_meta": {
    "enabled": ["state_machine","gate","review_contract","user_confirmation","symlink"],
    "spec_loaded": false,
    "truncate_enabled": true,
    "warnings": []
  }
}
```

### §11.1 `state_machine` detector

从 `attachment.hook_success` 的 `attachment.command` 字段提取 phase 转移轨迹。

默认正则：`^phase(\d+)\s+(pre|post)-([a-z0-9\-]+)`，匹配：
- `"phase0 pre-init workdir"` → phase=phase0, role=pre-init workdir
- `"phase4 post-summary"` → phase=phase4, role=post-summary

**输出**：
- `state_machine.phases`：去重保序的 phase 名列表
- `state_machine.transitions`：每条 `PhaseTransition`（含 phase / hook_event / trigger_entry_uuid / trigger_attachment_command / trigger_hook_name / at / role）
- `state_machine.unexpected_exits`：相邻 phase 跳跃 > 1 的边界

### §11.2 `gate` detector

识别 `*-gate.mjs` / `phase*-pre-*` 拒答事件。

**触发条件**：
- `entry_class == "attachment.hook_success"`
- `attachment.exitCode != 0`
- `attachment.command` 含 `gate` 或 `pre`

**输出**：`GateEvent`（含 `gate_script` / `phase` / `exit_code` / `stop_reason` / `evidence_ref` / `at` / `retry_seen_after`）。二轮扫描标记 `retry_seen_after`。

### §11.3 `review_contract` detector

识别 review-agent 调用契约违反。

**触发条件**：
- `entry_class == "ai_tool_call"`
- `message.content[*].name == "Agent"`
- `subagent_type` 含 `review` 子串

**检查项**（每个独立判定 spec 是否声明）：
1. `subagent_type_mismatch`：不在 `spec.subagents.review-agent.expected_subagent_types` 列表中
2. `missing_required_field`：tool_result 缺 `passed` / `retryAdvice` 字段（由 `spec.subagents.review-agent.required_fields` 驱动）
3. `retry_exceeded`：`retryCount > spec.subagents.review-agent.retry_count`

**spec 缺省时不做任何检查**（仅做存在性检测，不报错）。

### §11.4 `user_confirmation` detector

识别 AskUserQuestion / `[auto-confirm]` / `[Request interrupted]` 事件。

**触发条件**：
- `entry_class == "user_input"`
- `message.content` 含 `[Request interrupted...]` → mode=`interrupted`
- 含 `[auto-confirm]` → mode=`auto_confirm`
- `permissionMode` 显式设置 → mode=`explicit_<pm>`

**AUTO_CONFIRM 来源**：`env.AUTO_CONFIRM` / `env.AUTO_CONFIRM_USER_CONFIRMATION` / `spec.environment.auto_confirm_keys`（按顺序查找第一个有值的）。

### §11.5 `symlink` detector

检测 cwd 是否跳到物理源（symlink/junction）。

**触发条件**：
- `entry.cwd` 非空
- `os.path.realpath(cwd) != cwd`

**输出**：`SymlinkHopEvent`（含 `logical_cwd` / `physical_cwd` / `evidence_ref` / `at`）。

**v4 边界**：真实样本 single-cwd，1b4c0c37 上产 0 事件；v5 拿到 multi-cwd 数据后可启用强验证。Windows 上创建 symlink 需要管理员权限。

### §11.6 agent_spec 插件化

`specs/` 目录下 4 个 YAML 文件：

```yaml
# specs/spec.yaml — phases[] 列表
name: requirement_analysis
phases:
  - name: phase0
    roles: [pre-init, post-init]
  # ...

# specs/hooks.yaml — gates[] / post_hooks[] / stop_hooks[]
gates:
  - script: phase0-pre-init-workdir
    command: "phase0 pre-init workdir"
    blocks_skills: [查询需求信息]
# ...

# specs/subagents.yaml — review-agent 契约
review-agent:
  expected_subagent_types: [review-agent, 通用review-agent]
  retry_count: 2
  required_fields: [passed, retryAdvice]
# ...

# specs/constraints.yaml — 五层硬约束声明
constraints:
  - layer: CLAUDE.md
    rule: "..."
    detector: gate
# ...
```

detector 通过 `ctx.spec["phases"]` / `ctx.spec["subagents"]["review-agent"]` 等嵌套路径读取 spec 配置。spec 缺省时 detector 走默认规则。

### §11.7 detector 全文展开（v5 引入）

detector 命中需要全文展开时按 `evidence_ref`（uuid）查找原始 entry。调用约定：detector 默认只放 `evidence_ref`，不展开；上层 phase2 按需调用 `Detector.expand_full_ref(evidence_ref, raw_entries)`。

> **v4 历史**：早期 config 里有 `_META._EXPANDABLE_PATHS` 数组列出"可能需要展开的路径"，但**代码无人读**（detector 走 `expand_full_ref` 直接按 uuid 找原始 entry，不读这个数组）。v4 清理时已删除该字段。

---

## §12 v4 truncate 默认值变更

| 项 | v3 | v4 |
|---|---|---|
| `truncate_enabled` 默认值 | false | **true** |
| `_META._TRUNCATE` 启用条件 | 仅 `--truncate` 或 config `truncate_enabled: true` | 默认启用 |
| `keep_whole_if_is_error` | true（保留） | true（保留） |
| `message.content[*].text` 截断上限 | 6144 + 1024（启用时） | 6144 + 1024（默认即生效） |
| `message.content[*].content` / `toolUseResult.*` / `attachment.*` | 2048 + 1024（启用时） | 2048 + 1024（默认即生效） |

**实测影响**（1b4c0c37 真实样本）：
- `tool_result` 占 v3 输出 70%（17 条 82794B），默认截断后单条平均降至 ~5KB
- v3 减体积 -32.3%（190420B → 128833B）
- v4 减体积预估 -65%~75%（190420B → ~50-70KB）

**CLI 显式控制**：
```bash
# 默认即开启 truncation
python session_simplifier.py in.jsonl out.jsonl

# 显式关闭（v3 行为）
python session_simplifier.py in.jsonl out.jsonl --no-truncate

# 显式开启（与默认一致；冗余）
python session_simplifier.py in.jsonl out.jsonl --truncate
```

---

## §13 v4 detector 全局开关

```bash
# 跳过所有 detector（v3 行为）
python session_simplifier.py in.jsonl out.jsonl --no-detectors

# 仅启用指定 detector（可多次传）
python session_simplifier.py in.jsonl out.jsonl --detector state_machine --detector gate

# 传 agent_spec 目录
python session_simplifier.py in.jsonl out.jsonl --spec-dir specs/

# 静默模式
python session_simplifier.py in.jsonl out.jsonl --quiet
```

detector 启用列表由 `detector_meta.enabled` 字段记录到 header；spec 加载情况由 `detector_meta.spec_loaded` 字段记录。

---

## §14 v4 测试覆盖

| 测试文件 | 类型 | 覆盖 |
|---|---|---|
| `tests/test_models.py` | dataclass 单测 | ClassifiedEntry / EvidenceBundle / 5 个 detector 事件 dataclass |
| `tests/test_detector_state_machine.py` | detector 单测 | phase 识别 / 多 phase 保序 / phase 跳跃 / spec 覆盖 / 真实样本命令值 |
| `tests/test_detector_gate.py` | detector 单测 | exitCode=0 忽略 / exitCode=2 拒答 / retry_seen_after / stopReason 解析 |
| `tests/test_detector_review_contract.py` | detector 单测 | spec 缺省不报错 / missing_required_field / subagent_type_mismatch / retry_exceeded |
| `tests/test_detector_user_confirmation.py` | detector 单测 | interrupted / auto_confirm / permissionMode / env + spec auto_confirm_keys |
| `tests/test_detector_symlink.py` | detector 单测 | empty / no_cwd / realpath 缓存 / symlink 命中（Windows skip） |
| `tests/test_spec_loader.py` | spec_loader 单测 | None / 不存在 / 空目录 / 完整加载 / 部分缺失 |
| `tests/test_pipeline.py` | 伪样本 e2e | 5 类 detector 命中 / cwd_change / 整类型 DROP / truncate / spec 驱动 review_contract |
| `tests/test_pipeline_real.py` | 真实样本 e2e | 需 RUN_REAL=1；识别 phase0/phase4 + gate_rejected + spec_loaded |
| `tests/test_v3_compat.py` | v3 兼容回归 | header 字段保留 / trace count / trace union keys / schema_version 仅在 header |
| `tests/test_integration.py` | v3 兼容回归（已改造） | 跨平台 Path(__file__).parent 路径；test_with_real_session 不再 skip |
| `tests/test_classifier.py` / `test_simplifier.py` / `test_timestamp.py` / `test_utils.py` | v3 复用 | 保持 v3 行为不变 |