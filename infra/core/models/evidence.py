"""Data models for session evidence."""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime


@dataclass
class TokenUsage:
    """Token usage statistics."""
    input: int = 0
    output: int = 0


@dataclass
class ToolCall:
    """Represents a tool call in a session."""
    uuid: str = ""
    tool_name: str = ""
    tool_use_id: str = ""
    input_summary: str = ""
    output_summary: str = ""
    success: bool = True
    error_message: Optional[str] = None
    error_output: Optional[str] = None
    duration_ms: int = 0
    timestamp: Optional[str] = None
    reasoning: Optional[str] = None
    agent_id: str = ""
    agent_type: str = ""


@dataclass
class ExecutionSummary:
    """Execution summary for a skill or session."""
    total_tool_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    total_duration_ms: int = 0
    token_usage: TokenUsage = field(default_factory=TokenUsage)
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_tool_calls == 0:
            return 0.0
        return self.successful_calls / self.total_tool_calls
    
    @property
    def success_level(self) -> str:
        """Get success level description."""
        rate = self.success_rate
        if rate >= 0.9:
            return "excellent"
        elif rate >= 0.7:
            return "good"
        elif rate >= 0.5:
            return "fair"
        else:
            return "poor"


@dataclass
class SessionContext:
    """Context information for a session."""
    user_query: str = ""
    session_type: str = ""
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    cwd: str = ""
    version: str = ""
    git_branch: str = ""
    user_command: str = ""
    requirement_id: str = ""


@dataclass
class SkillEvidence:
    """Evidence for a single skill execution."""
    skill_name: str = ""
    tool_calls: List[ToolCall] = field(default_factory=list)
    execution_summary: ExecutionSummary = field(default_factory=ExecutionSummary)
    context: SessionContext = field(default_factory=SessionContext)
    session_id: str = ""
    file_path: str = ""
    stage: str = ""
    skill_definition: str = ""
    files_read: List[str] = field(default_factory=list)
    files_written: List[str] = field(default_factory=list)
    retry_chains: List[List[ToolCall]] = field(default_factory=list)


@dataclass
class SessionEvidence:
    """Evidence extracted from a session."""
    session_id: str = ""
    file_path: str = ""
    session_path: str = ""
    skill_evidences: List[SkillEvidence] = field(default_factory=list)
    skills: List[SkillEvidence] = field(default_factory=list)
    execution_summary: ExecutionSummary = field(default_factory=ExecutionSummary)
    context: SessionContext = field(default_factory=SessionContext)
    total_tool_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    skill_pack: str = "unknown"
    session_outcome: str = ""
    total_message_count: int = 0


__all__ = [
    'TokenUsage', 'ToolCall', 'ExecutionSummary',
    'SessionContext', 'SkillEvidence', 'SessionEvidence'
]
