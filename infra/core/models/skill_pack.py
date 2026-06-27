"""Skill pack configuration models."""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class SkillConfig(BaseModel):
    """Skill configuration."""
    name: str
    description: str = ""
    file_path: str = ""


class AgentConfig(BaseModel):
    """Agent configuration."""
    name: str
    description: str = ""
    file_path: str = ""


class StageConfig(BaseModel):
    """Stage configuration."""
    name: str
    description: str = ""
    skills: List[str] = Field(default_factory=list)
    agents: List[str] = Field(default_factory=list)
    next_stages: List[str] = Field(default_factory=list)


class TopologyNode(BaseModel):
    """Topology node."""
    name: str
    type: str  # "skill", "agent", "stage", "command"
    children: List[str] = Field(default_factory=list)


class SkillPackConfig(BaseModel):
    """Skill pack configuration."""
    name: str
    description: str = ""
    version: str = "1.0.0"
    skills: List[SkillConfig] = Field(default_factory=list)
    agents: List[AgentConfig] = Field(default_factory=list)
    stages: List[StageConfig] = Field(default_factory=list)
    topology: List[TopologyNode] = Field(default_factory=list)
    entry_keywords: List[str] = Field(default_factory=list)  # 用于识别session属于哪个技能包


def load_skill_pack(pack_path: str) -> SkillPackConfig:
    """Load skill pack configuration from JSON file."""
    import json
    with open(pack_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return SkillPackConfig(**data)
