"""
v4 数据模型 — dataclass + to_dict()，不依赖 pydantic。

定义：
- ClassifiedEntry: 单条已被 classifier 标过 entry_class 的 entry
- EvidenceBundle: v4 collector 产出的完整证据包
- 5 个 detector 的事件 dataclass（PhaseTransition / GateEvent / ReviewContractEvent /
  UserConfirmationEvent / SymlinkHopEvent）
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# 基础容器
# ---------------------------------------------------------------------------


@dataclass
class ClassifiedEntry:
    """已被 classifier 标过 entry_class 的单条 entry。"""

    raw: Dict[str, Any]
    entry_class: str

    def uuid(self) -> Optional[str]:
        return self.raw.get("uuid")

    def timestamp(self) -> str:
        return self.raw.get("timestamp", "")


@dataclass
class DetectorContext:
    """detector 共享的不可变上下文快照。"""

    spec: Dict[str, Any] = field(default_factory=dict)
    env: Dict[str, str] = field(default_factory=dict)
    cwd_realpath_cache: Dict[str, str] = field(default_factory=dict)


@dataclass
class EvidenceBundle:
    """v4 collector 完整输出（顶层 schema）。"""

    schema_version: str
    session: Dict[str, Any]
    cwd_changes: int
    trace: List[Dict[str, Any]]
    state_machine: Dict[str, Any]
    constraint_events: List[Dict[str, Any]]
    user_feedback: List[Dict[str, Any]]
    execution_pattern: Dict[str, Any]
    detector_meta: Dict[str, Any]
    symlink_hop: List[Dict[str, Any]] = field(default_factory=list)     # symlink detector 事件

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# detector 事件 dataclass
# ---------------------------------------------------------------------------


@dataclass
class PhaseTransition:
    phase: str
    hook_event: str
    trigger_entry_uuid: str
    trigger_attachment_command: str
    trigger_hook_name: Optional[str]
    at: str
    role: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class GateEvent:
    kind: str
    gate_script: str
    phase: Optional[str]
    blocked_skill: Optional[str]
    exit_code: int
    stop_reason: str
    evidence_ref: str
    at: str
    retry_seen_after: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ReviewContractEvent:
    kind: str
    issue: str
    reviewer_subagent_type: str
    expected_subagent_types: List[str]
    actual_subagent_type: Optional[str]
    retry_count: int
    evidence_ref: str
    at: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class UserConfirmationEvent:
    kind: str
    mode: str
    trigger: str
    evidence_ref: str
    at: str
    auto_confirm_env: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SymlinkHopEvent:
    kind: str
    logical_cwd: str
    physical_cwd: str
    evidence_ref: str
    at: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)