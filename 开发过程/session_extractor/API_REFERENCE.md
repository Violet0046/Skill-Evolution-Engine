# v4 Collector — API 参考

> 字段保留规范见 [entry_fields_spec.md](entry_fields_spec.md)；架构总览见 [ARCHITECTURE.md](ARCHITECTURE.md)；输出示例见 [EXAMPLES.md](EXAMPLES.md)；CLI 用法见 [README.md](README.md)。

---

## 1. detector 注册表

| name (`@register`) | class | spec 依赖路径 | env keys | 输出事件字段 |
|---|---|---|---|---|
| `state_machine` | `StateMachineDetector` | `ctx.spec["phases"][].name` | — | `kind=state_machine`, `phases: list[str]`, `transitions: list[PhaseTransition]`, `unexpected_exits: list[PhaseTransition]` |
| `gate` | `GateDetector` | — | — | `kind=gate_rejected`, `gate_script`, `phase`, `blocked_skill`, `exit_code`, `stop_reason`, `evidence_ref`, `at`, `retry_seen_after` |
| `review_contract` | `ReviewContractDetector` | `ctx.spec["subagents"]["review-agent"].{expected_subagent_types, required_fields, retry_count}` | — | `kind=review_contract`, `issue` ∈ {`subagent_type_mismatch`, `missing_required_field`, `retry_exceeded`}, `reviewer_subagent_type`, `expected_subagent_types`, `actual_subagent_type`, `retry_count`, `evidence_ref`, `at` |
| `user_confirmation` | `UserConfirmationDetector` | `ctx.spec["environment"]["auto_confirm_keys"][]` | `AUTO_CONFIRM`, `AUTO_CONFIRM_USER_CONFIRMATION` | `kind=user_confirmation`, `mode` ∈ {`interrupted`, `auto_confirm`, `explicit_<permissionMode>`}, `trigger`, `evidence_ref`, `at`, `auto_confirm_env` |
| `symlink` | `SymlinkHopDetector` | — | — | `kind=symlink_hop`, `logical_cwd`, `physical_cwd`, `evidence_ref`, `at` |

### 1.1 触发条件速查

| detector | entry_class | 关键字段 |
|---|---|---|
| state_machine | `attachment.hook_success` | `attachment.command` 匹配 `^phase\d+\s+(pre\|post)-[a-z0-9\-]+` |
| gate | `attachment.hook_success` | `attachment.exitCode != 0` + `attachment.command` 含 `gate` 或 `pre` |
| review_contract | `ai_tool_call` | `message.content[*].name == "Agent"` + `input.subagent_type` 含 `review` |
| user_confirmation | `user_input` | `message.content` 含 `[Request interrupted...]` / `[auto-confirm]`；或 `permissionMode` 显式设置 |
| symlink | 任意带 `cwd` | `os.path.realpath(cwd) != cwd` |

### 1.2 新增 detector 的契约

```python
# src/detectors/foo.py
from .base import Detector, register
from src.models import ClassifiedEntry, DetectorContext


@register("foo")  # 必须；与 pipeline 默认 enabled 列表同步
class FooDetector(Detector):
    def run(self, entries: List[ClassifiedEntry], ctx: DetectorContext) -> List[Dict[str, Any]]:
        # 返回事件 dict 列表；空列表表示 0 命中
        return [{"kind": "foo", "evidence_ref": e.uuid(), "at": e.timestamp()} for e in entries if ...]
```

然后在 `src/detectors/__init__.py` 的 `_import_all()` 列表加 `"foo"`。

---

## 2. `EvidenceBundle` 字段说明

| 字段 | 类型 | 来源 | 说明 |
|---|---|---|---|
| `schema_version` | `str` | 常量 `"4.0"` | 第 1 行 header 第 1 个字段；用于下游 v3/v4 路由 |
| `session` | `Dict[str, Any]` | `io.extract_session_header` + 注入 `start_time`/`end_time` | 6 字段 v3 兼容（sessionId/version/entrypoint/isSidechain/userType/cwd）+ 2 扩展（start_time/end_time） |
| `cwd_changes` | `int` | `io.insert_cwd_changes` 返值 | cwd 跳变计数（v3 字段名 `cwdChanges` 的 snake_case 版） |
| `trace` | `List[Dict]` | `simplify_entries` 输出 | 字段集与 v3 完全一致；写盘时 `pop` 出来走 NDJSON 第 2+ 行 |
| `state_machine` | `Dict` | `state_machine` detector 或 `make_empty_bundle()` 兜底 | 嵌套：`phases: list[str]` / `transitions: list[PhaseTransition]` / `unexpected_exits: list[PhaseTransition]` |
| `constraint_events` | `List[Dict]` | `gate` + `review_contract` 合并 | `kind` 字段区分（`gate_rejected` / `review_contract`） |
| `user_feedback` | `List[Dict]` | `user_feedback.extract_user_feedback` | `{uuid, text, timestamp}` |
| `execution_pattern` | `Dict` | `execution_pattern.compute_execution_pattern` | `step_counts` / `retry_loops` (留空) / `tool_distribution` / `phase_durations` |
| `detector_meta` | `Dict` | pipeline 装配 | `enabled: list[str]` / `spec_loaded: bool` / `truncate_enabled: bool` / `warnings: list[str]` |

### 2.1 嵌套 schema 速查

**state_machine.transitions[]**（`PhaseTransition`）：
```json
{"phase": "phase0", "hook_event": "PreToolUse", "trigger_entry_uuid": "...",
 "trigger_attachment_command": "phase0 pre-init workdir",
 "trigger_hook_name": "PreToolUse:Skill", "at": "...", "role": "pre-init workdir"}
```

**execution_pattern.step_counts**（按 entry_class 计数）：
```json
{"user_input": 4, "ai_text": 16, "ai_tool_call": 17, "tool_result": 17,
 "attachment.hook_success": 18, "user_command": 3}
```

**detector_meta**：
```json
{"enabled": ["state_machine", "gate", "review_contract", "user_confirmation", "symlink"],
 "spec_loaded": true, "truncate_enabled": true, "warnings": []}
```

---

## 3. `ClassifiedEntry` / `DetectorContext` 字段说明

### 3.1 `ClassifiedEntry`（`src/models.py`）

| 字段 | 类型 | 说明 |
|---|---|---|
| `raw` | `Dict[str, Any]` | 原始 entry dict（未经 simplify） |
| `entry_class` | `str` | 已分类（含 `attachment.{subtype}` 细化） |

| 方法 | 返回 | 说明 |
|---|---|---|
| `.uuid()` | `Optional[str]` | `raw["uuid"]` |
| `.timestamp()` | `str` | `raw["timestamp"]`（空串兜底） |

### 3.2 `DetectorContext`（`src/models.py`）

| 字段 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `spec` | `Dict[str, Any]` | `{}` | 平铺后嵌套路径不变的 spec（detector 按嵌套路径读） |
| `env` | `Dict[str, str]` | `{}` | `os.environ` 副本 |
| `cwd_realpath_cache` | `Dict[str, str]` | `{}` | symlink detector 用的 realpath 缓存（**唯一带跨调用副作用**） |

### 3.3 5 个事件 dataclass

| dataclass | 字段 |
|---|---|
| `PhaseTransition` | phase, hook_event, trigger_entry_uuid, trigger_attachment_command, trigger_hook_name, at, role |
| `GateEvent` | kind, gate_script, phase, blocked_skill, exit_code, stop_reason, evidence_ref, at, retry_seen_after |
| `ReviewContractEvent` | kind, issue, reviewer_subagent_type, expected_subagent_types, actual_subagent_type, retry_count, evidence_ref, at |
| `UserConfirmationEvent` | kind, mode, trigger, evidence_ref, at, auto_confirm_env |
| `SymlinkHopEvent` | kind, logical_cwd, physical_cwd, evidence_ref, at |

每个 dataclass 都有 `to_dict()` 方法（`dataclasses.asdict`）。

---

## 4. spec YAML 4 文件字段说明

| 文件 | 顶层 key | 字段 | detector 读取方 |
|---|---|---|---|
| `specs/spec.yaml` | `spec` | `name: str`, `version: str`, `phases[]: [{name, description, roles[]}]` | state_machine（读 `phases[].name`） |
| `specs/hooks.yaml` | `hooks` | `gates[]: [{script, command, blocks_skills[], expected_exit}]`, `post_hooks[]`, `stop_hooks[]` | （v5 启用） |
| `specs/subagents.yaml` | `subagents` | `review-agent: {expected_subagent_types[], required_fields[], retry_count, caller_phases[]}` | review_contract |
| `specs/constraints.yaml` | `constraints` | `[]: [{layer, rule, detector}]` | （v5 启用） |

### 4.1 spec 完整示例

`specs/spec.yaml`：
```yaml
name: requirement_analysis
version: "1.0"
phases:
  - name: phase0
    description: 初始化准备
    roles: [pre-init, post-init]
  - name: phase4
    description: 阶段4 - 需求总结
    roles: [post-summary]
```

`specs/subagents.yaml`：
```yaml
review-agent:
  expected_subagent_types: [review-agent, 通用review-agent]
  retry_count: 2
  required_fields: [passed, retryAdvice]
  caller_phases: [phase3]
```

---

## 5. `pipeline.run()` 函数签名

```python
def run(
    input_path: str,
    output_path: str,
    config_path: Optional[str] = None,
    spec_dir: Optional[str] = None,
    simplify: bool = True,
    truncate: Optional[bool] = None,  # None = 用 config 默认值
    enabled_detectors: Optional[List[str]] = None,
    skip_detectors: bool = False,
    env: Optional[Dict[str, str]] = None,
    quiet: bool = False,
) -> EvidenceBundle:
```

| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `input_path` | `str` | (必填) | session JSONL 或 JSON-array 文件路径 |
| `output_path` | `str` | (必填) | 输出文件路径（第 1 行 header + 后续 NDJSON） |
| `config_path` | `Optional[str]` | `None` | `entry_fields_config.json` 路径；None 时不 simplify |
| `spec_dir` | `Optional[str]` | `None` | `specs/` 目录路径；None 时 detector 走默认规则 |
| `simplify` | `bool` | `True` | 是否运行字段精简 |
| `truncate` | `Optional[bool]` | `None` | `True`/`False`/`None`（用 config） |
| `enabled_detectors` | `Optional[List[str]]` | `None` | 启用子集；`None` 时跑全部 5 个 |
| `skip_detectors` | `bool` | `False` | `True` 时跳过全部 detector（v3 行为） |
| `env` | `Optional[Dict[str, str]]` | `None` | 环境变量副本；None 时用 `os.environ` |
| `quiet` | `bool` | `False` | 静默模式（不打印 INFO 日志） |

返回 `EvidenceBundle`（同时写盘到 `output_path`）。

---

## 6. CLI 参数（`run.py` / `session_simplifier.py`）

```
run.py [-h] [--no-simplify] [--truncate] [--no-truncate]
       [--no-detectors] [--detector DETECTOR]
       [--spec-dir SPEC_DIR] [--write-config-defaults]
       [--quiet]
       input_file output_file
```

| 参数 | 说明 |
|---|---|
| `input_file` / `output_file` | 位置参数；session 输入 + 输出路径 |
| `--no-simplify` | 禁用字段精简（保留全部字段） |
| `--truncate` | 显式启用 truncation（v4 默认即开启，冗余兼容） |
| `--no-truncate` | 显式关闭 truncation（v3 行为） |
| `--no-detectors` | 跳过所有 detector（v3 行为） |
| `--detector X` | 仅启用指定 detector（可多次传） |
| `--spec-dir Y` | agent_spec YAML 目录 |
| `--write-config-defaults` | 一次性把 `truncate_enabled=true` 写回 `entry_fields_config.json` |
| `--quiet` | 静默模式（不打印 INFO 日志） |

`session_simplifier.py` 是 12 行 alias，行为与 `run.py` **完全一致**（双入口 diff 应为空）。