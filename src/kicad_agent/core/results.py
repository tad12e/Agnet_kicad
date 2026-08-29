"""Result structures for action execution and verification."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .errors import AgentError


@dataclass
class ActionResult:
    """Outcome of an individual Action execution.
    
    Attributes:
        action_id: The ID of the action executed.
        success: Whether backend execution completed without failure.
        data: Return data or created object snapshot.
        error: Structured AgentError if execution failed.
        execution_time_ms: Duration of backend execution in milliseconds.
        backend_used: Name of the backend that executed this action.
    """
    action_id: str
    success: bool
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[AgentError] = None
    execution_time_ms: float = 0.0
    backend_used: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Serialize result to dictionary."""
        return {
            "action_id": self.action_id,
            "success": self.success,
            "data": self.data,
            "error": self.error.to_dict() if self.error else None,
            "execution_time_ms": self.execution_time_ms,
            "backend_used": self.backend_used,
        }


@dataclass
class VerificationResult:
    """Outcome of a verification check on action or goal completion.
    
    Attributes:
        verifier_name: Name of the verifier (e.g. PlacementVerifier).
        passed: Whether the verification assertion was satisfied.
        message: Diagnostic explanation of check outcome.
        details: Quantitative verification metrics (e.g. coordinates, distance).
        violations: List of specific rule or intent violations found.
        timestamp: Unix timestamp when check ran.
    """
    verifier_name: str
    passed: bool
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    violations: List[Dict[str, Any]] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize verification result to dictionary."""
        return {
            "verifier_name": self.verifier_name,
            "passed": self.passed,
            "message": self.message,
            "details": self.details,
            "violations": self.violations,
            "timestamp": self.timestamp,
        }
