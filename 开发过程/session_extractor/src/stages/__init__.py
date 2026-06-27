"""stages/ 子目录：pipeline 的各个处理阶段。

- execution_pattern.py: 行为模式统计（step_counts / tool_distribution / phase_durations）
- user_feedback.py:     user_input 文本提取
- bundle_writer.py:     EvidenceBundle 兜底 + 写出

每个 stage 由 pipeline.run() 顺序调用，输出合并到 EvidenceBundle 的对应字段。
"""

from .execution_pattern import compute_execution_pattern
from .user_feedback import extract_user_feedback
from .bundle_writer import (
    make_empty_bundle,
    write_bundle,
)

__all__ = [
    "compute_execution_pattern",
    "extract_user_feedback",
    "make_empty_bundle",
    "write_bundle",
]