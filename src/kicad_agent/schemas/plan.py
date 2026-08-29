"""Plan validation schemas."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from .action import ActionSchema


class GoalSchema(BaseModel):
    """Schema for validating design goals."""
    goal_type: str
    description: str = ""
    targets: List[str] = Field(default_factory=list)
    criteria: Dict[str, Any] = Field(default_factory=dict)


class PlanSchema(BaseModel):
    """Schema for validating action execution plans."""
    goals: List[GoalSchema] = Field(default_factory=list)
    actions: List[ActionSchema] = Field(default_factory=list)
    dependencies: Dict[str, List[str]] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
