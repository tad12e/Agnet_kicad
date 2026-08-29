"""Error schemas."""

from __future__ import annotations

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class AgentErrorSchema(BaseModel):
    error_id: str = ""
    category: str
    severity: str = "error"
    message: str
    operation: Optional[str] = None
    target_object: Optional[str] = None
    context: Dict[str, Any] = Field(default_factory=dict)
    recoverable: bool = True
