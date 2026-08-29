"""Action validation schemas using Pydantic."""

from __future__ import annotations

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class ActionSchema(BaseModel):
    """Schema for validating structured actions."""
    action_type: str = Field(..., description="Action identifier enum")
    domain: str = Field("pcb", description="Target domain: pcb, schematic, system")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Action arguments")
    description: Optional[str] = Field("", description="Human-readable explanation")
    expected_outcome: Optional[Dict[str, Any]] = None
