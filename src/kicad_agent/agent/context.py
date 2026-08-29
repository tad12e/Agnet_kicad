"""Context and session tracking for design requests."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class DesignConstraints:
    """Constraints applied to the current design session."""
    min_trace_width_mm: float = 0.2
    min_clearance_mm: float = 0.2
    min_component_spacing_mm: float = 2.5
    default_grid_mm: float = 1.27
    board_width_mm: Optional[float] = None
    board_height_mm: Optional[float] = None


@dataclass
class AgentContext:
    """Context holding design constraints, preferences, and session history."""
    constraints: DesignConstraints = field(default_factory=DesignConstraints)
    user_preferences: Dict[str, Any] = field(default_factory=dict)
    conversation_history: List[Dict[str, Any]] = field(default_factory=list)
