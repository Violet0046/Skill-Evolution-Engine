"""Configuration for extractors."""

from dataclasses import dataclass


@dataclass
class ExtractorConfig:
    """Configuration for session extractor."""
    max_input_summary: int = 200
    max_error_output: int = 500
    max_output_summary: int = 200
    max_reasoning: int = 500
    max_skill_definition: int = 2000
    extract_reasoning: bool = True
    extract_file_io: bool = True
    extract_output_summary: bool = True
    extract_retry_chains: bool = True
    extract_skill_definition: bool = True


DEFAULT_CONFIG = ExtractorConfig()
