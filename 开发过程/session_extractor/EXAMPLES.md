# v4 Collector — 输出示例

> 本文件用 `1b4c0c37-23cc-4e75-9eb9-125629d9d274.jsonl` 真实样本（91 条 entry）展示 3 种典型输出。
> 字段保留规范见 [entry_fields_spec.md](entry_fields_spec.md)；架构总览见 [ARCHITECTURE.md](ARCHITECTURE.md)；API 参考见 [API_REFERENCE.md](API_REFERENCE.md)；CLI 用法见 [README.md](README.md)。

---

## 1. 正常路径（5 detector 部分命中）

**命令**：
```bash
python run.py 1b4c0c37-23cc-4e75-9eb9-125629d9d274.jsonl out_normal.jsonl --spec-dir specs/
```

### 1.1 第 1 行 header（完整 JSON，填值后）

```json
{
  "schema_version": "4.0",
  "session": {
    "sessionId": "1b4c0c37-23cc-4e75-9eb9-125629d9d274",
    "version": "2.1.132",
    "entrypoint": "sdk-ts",
    "isSidechain": false,
    "userType": "external",
    "cwd": "/home/10103128@zte.intra/sdd/01-需求分析/ran_design_sdd-test-iMate_masterAgent/需求分析Agent",
    "start_time": "2026-05-09T03:07:09.817Z",
    "end_time": "2026-05-09T03:56:49.765Z"
  },
  "cwd_changes": 0,
  "state_machine": {
    "phases": ["phase0", "phase4"],
    "transitions": [
      {
        "phase": "phase0",
        "hook_event": "PreToolUse",
        "trigger_entry_uuid": "<idx-34-uuid>",
        "trigger_attachment_command": "phase0 pre-init workdir",
        "trigger_hook_name": "PreToolUse:Skill",
        "at": "2026-05-09T03:07:35.123Z",
        "role": "pre-init workdir"
      },
      {
        "phase": "phase4",
        "hook_event": "Stop",
        "trigger_entry_uuid": "<idx-89-uuid>",
        "trigger_attachment_command": "phase4 post-summary",
        "trigger_hook_name": "Stop",
        "at": "2026-05-09T03:56:48.456Z",
        "role": "post-summary"
      }
    ],
    "unexpected_exits": []
  },
  "constraint_events": [
    {
      "kind": "gate_rejected",
      "gate_script": "phase0-pre-init-workdir",
      "phase": "phase0",
      "blocked_skill": null,
      "exit_code": 2,
      "stop_reason": "无法提取需求ID",
      "evidence_ref": "<idx-34-uuid>",
      "at": "2026-05-09T03:07:35.123Z",
      "retry_seen_after": true
    }
  ],
  "user_feedback": [
    {"uuid": "<idx-1-uuid>", "text": "请跳过查询过程，已有相关需求信息", "timestamp": "2026-05-09T03:07:09.998Z"},
    {"uuid": "<idx-2-uuid>", "text": "明白，已跳过查询。", "timestamp": "..."}
  ],
  "execution_pattern": {
    "step_counts": {
      "user_input": 4,
      "ai_text": 16,
      "ai_tool_call": 17,
      "tool_result": 17,
      "attachment.hook_success": 18,
      "user_command": 3
    },
    "retry_loops": [],
    "tool_distribution": {
      "Read": 9,
      "Bash": 4,
      "Edit": 1,
      "Skill": 1,
      "Agent": 1
    },
    "phase_durations": {
      "phase0": {"start": "2026-05-09T03:07:35.123Z", "end": "2026-05-09T03:07:35.123Z"},
      "phase4": {"start": "2026-05-09T03:56:48.456Z", "end": "2026-05-09T03:56:48.456Z"}
    }
  },
  "detector_meta": {
    "enabled": ["state_machine", "gate", "review_contract", "user_confirmation", "symlink"],
    "spec_loaded": true,
    "truncate_enabled": true,
    "warnings": []
  }
}
```

### 1.2 后续 NDJSON trace 摘要（每条 entry 一行，字段集与 v3 完全一致）

```jsonl
{"uuid":"<idx-0-uuid>","parentUuid":null,"timestamp":"2026-05-09T03:07:09.817Z","type":"user","message":{"content":[{"type":"text","text":"..."}]},"entry_class":"user_input"}
{"uuid":"<idx-1-uuid>","parentUuid":"<idx-0-uuid>","timestamp":"2026-05-09T03:07:09.998Z","type":"user","message":{"content":[{"type":"text","text":"请跳过查询过程，已有相关需求信息"}]},"entry_class":"user_input"}
{"uuid":"<idx-2-uuid>","parentUuid":"<idx-1-uuid>","timestamp":"2026-05-09T03:07:15.310Z","type":"assistant","message":{"content":[{"type":"text","text":"<think>...</think>明白，已跳过查询。"}],"stop_reason":"end_turn"},"entry_class":"ai_text"}
{"uuid":"<idx-33-uuid>","parentUuid":"<idx-32-uuid>","timestamp":"2026-05-09T03:07:35.120Z","type":"assistant","message":{"content":[{"type":"tool_use","id":"<call-1>","name":"Skill","input":{"skill":"查询需求信息"}}]},"entry_class":"ai_tool_call"}
{"uuid":"<idx-34-uuid>","parentUuid":"<idx-33-uuid>","timestamp":"2026-05-09T03:07:35.123Z","type":"attachment","attachment":{"type":"hook_success","hookName":"PreToolUse:Skill","hookEvent":"PreToolUse","command":"phase0 pre-init workdir","exitCode":2,"durationMs":68,"stderr":"[phase0-pre-init-workdir] blocked","stdout":"{\"continue\":false,\"stopReason\":\"blocked\"}"},"entry_class":"attachment.hook_success"}
{"uuid":"<idx-35-uuid>","parentUuid":"<idx-34-uuid>","timestamp":"2026-05-09T03:07:36.001Z","type":"user","message":{"content":[{"type":"tool_result","tool_use_id":"<call-1>","content":"...","is_error":true}]},"sourceToolAssistantUUID":"<idx-33-uuid>","entry_class":"tool_result"}
...
{"uuid":"<idx-89-uuid>","parentUuid":"<idx-88-uuid>","timestamp":"2026-05-09T03:56:48.456Z","type":"attachment","attachment":{"type":"hook_success","hookName":"Stop","hookEvent":"Stop","command":"phase4 post-summary","exitCode":0,"durationMs":72,"stdout":"{\"continue\":true}"},"entry_class":"attachment.hook_success"}
{"uuid":"<idx-90-uuid>","parentUuid":"<idx-89-uuid>","timestamp":"2026-05-09T03:56:49.765Z","type":"assistant","message":{"content":[{"type":"text","text":"完成需求分析"}],"stop_reason":"end_turn"},"entry_class":"ai_text"}
```

**总行数**：75 条 trace（91 entry - 16 整类型 DROP / 重复）。

### 1.3 关键观察

- `state_machine.phases` 识别到 2 个 phase（phase0 + phase4），缺失 phase1/2/3 在该 session 中未触发对应 hook
- `state_machine.unexpected_exits` 为空（phase0 → phase4 是 Stop 触发结束，不算跳跃）
- `constraint_events[0].retry_seen_after = true`：idx-34 拒答后 idx-35 立刻出现 retry（tool_result is_error=true）
- `user_feedback` 含 2 条用户输入文本
- `execution_pattern.step_counts.user_input = 4`：91 entry 中只有 4 条用户真实输入，其余 13 条 user_command 是系统注入命令
- `cwd_changes = 0`：该 session cwd 全程不变（spec §验证数据称 153/167 是 single-cwd）

---

## 2. 空输入兜底

**命令**：
```bash
# 输入文件为空
python run.py empty.jsonl out_empty.jsonl
```

### 2.1 第 1 行 header（完整 JSON）

```json
{
  "schema_version": "4.0",
  "session": {
    "sessionId": null,
    "version": null,
    "entrypoint": null,
    "isSidechain": null,
    "userType": null,
    "cwd": null,
    "start_time": null,
    "end_time": null
  },
  "cwd_changes": 0,
  "state_machine": {"phases": [], "transitions": [], "unexpected_exits": []},
  "constraint_events": [],
  "user_feedback": [],
  "execution_pattern": {
    "step_counts": {},
    "retry_loops": [],
    "tool_distribution": {},
    "phase_durations": {}
  },
  "detector_meta": {
    "enabled": [],
    "spec_loaded": false,
    "truncate_enabled": false,
    "warnings": []
  }
}
```

### 2.2 后续 NDJSON trace

**输出文件只有这一行**（无 NDJSON trace 行）。

### 2.3 关键观察

- `session` 6 字段全部为 `null`
- `start_time` / `end_time` 也为 `null`（无 entry 可取）
- `detector_meta.enabled = []` 空数组：兜底时 detector 全部未跑
- `detector_meta.spec_loaded = false`：未传 `--spec-dir`
- `detector_meta.truncate_enabled = false`：simplify 没跑（无 config）

---

## 3. `--no-detectors` 行为

**命令**：
```bash
python run.py 1b4c0c37-23cc-4e75-9eb9-125629d9d274.jsonl out_skip.jsonl --no-detectors
```

### 3.1 第 1 行 header（与正常路径对比）

```json
{
  "schema_version": "4.0",
  "session": { "...": "..." },
  "cwd_changes": 0,
  "state_machine": {"phases": [], "transitions": [], "unexpected_exits": []},
  "constraint_events": [],
  "user_feedback": [...],
  "execution_pattern": {
    "step_counts": { "...": "..." },
    "retry_loops": [],
    "tool_distribution": { "...": "..." },
    "phase_durations": {}
  },
  "detector_meta": {
    "enabled": [],
    "spec_loaded": true,
    "truncate_enabled": true,
    "warnings": ["detectors skipped"]
  }
}
```

### 3.2 关键观察

- `state_machine` / `constraint_events` / `phase_durations` 全部为空（detector 没跑）
- `user_feedback` 仍正常（user_feedback 提取与 detector 无关）
- `execution_pattern.step_counts` / `tool_distribution` 仍正常（统计与 detector 无关）
- `detector_meta.warnings = ["detectors skipped"]`：标记用户行为
- `detector_meta.enabled = []`：明示无 detector 运行
- NDJSON trace 字段集与正常路径**完全相同**（`--no-detectors` 只影响 detector 事件，不影响 classify / sort / simplify / write）

---

## 4. 体积对比（1b4c0c37 真实样本）

| 版本 | 字节 | 占比 | 关键差异 |
|---|---|---|---|
| 原始 | 190,420 | 100.0% | NDJSON / JSON-array 91 条 entry |
| v3 out.jsonl | 128,833 | **67.7%** | 整类型 DROP 16 条 + 字段白名单精简 |
| v4 out.jsonl | 113,577 | **59.6%** | v3 行为 + 默认 truncate ON |

**v4 比 v3 又小 11.8%**：truncate 默认 ON 让 `tool_result` 大字段（最大 17KB）压到 ~5KB 平均；新增 detector 事件 + spec_loaded 字段合计 ~4KB。**净效应是体积更小**。

---

## 5. 与 v3 trace NDJSON 的兼容性

| 项 | v3 | v4 | 一致性 |
|---|---|---|---|
| 第 1 行字段 | `session` / `cwdChanges` | `schema_version` / `session` / `cwd_changes` / 6 扩展 | 兼容（v4 含 v3 全部键） |
| `cwdChanges` vs `cwd_changes` | camelCase | snake_case | **不同**（已显式允许） |
| 第 2+ 行字段集 | 10 keys union | 10 keys union | **完全相同** |
| 单条 entry 的 entry_class | 同 v4 | 同 v3 | 完全相同 |

**v3 消费者读 v4 输出**：
```python
# 只读 v3 字段的消费者照常工作
with open("out_v4.jsonl") as f:
    header = json.loads(f.readline())  # 含 session, cwdChanges (无，v4 改名 cwd_changes)
    for line in f:
        entry = json.loads(line)
        print(entry["entry_class"])  # 完全兼容
```

完整兼容性测试见 `tests/test_v3_compat.py`。