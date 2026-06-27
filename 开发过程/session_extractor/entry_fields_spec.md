# Session Entry 字段保留规范 (v3)

## 目标

精简 Claude Code session JSONL，**目的**是让下游 LLM **找到"需求分析 agent"在执行中暴露的问题**（skill 执行逻辑、agents 配置、prompt、工作流），进而**进化该 agent**。

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

## 字段保留原则

1. **必须保留 (required)**：理解 agent 行为和决策的关键
2. **建议保留 (recommended)**：对分析和改进有帮助
3. **可选保留 (optional)**：完整性但不关键
4. **不保留 (drop)**：对进化目标无价值

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