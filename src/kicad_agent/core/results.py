"""Result structures for action execution and verification."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .errors import AgentError, ErrorCategory, ErrorSeverity


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

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ActionResult":
        error_data = data.get("error")
        error = None
        if error_data:
            error = AgentError(
                error_id=error_data.get("error_id", ""),
                category=ErrorCategory(
                    error_data.get("category", ErrorCategory.UNKNOWN_ERROR.value)
                ),
                severity=ErrorSeverity(
                    error_data.get("severity", ErrorSeverity.ERROR.value)
                ),
                message=error_data.get("message", ""),
                operation=error_data.get("operation"),
                target_object=error_data.get("target_object"),
                context=dict(error_data.get("context", {})),
                recoverable=bool(error_data.get("recoverable", True)),
            )
        return cls(
            action_id=data["action_id"],
            success=bool(data.get("success", False)),
            data=dict(data.get("data", {})),
            error=error,
            execution_time_ms=float(data.get("execution_time_ms", 0.0)),
            backend_used=data.get("backend_used", ""),
        )


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
    # ``not_verifiable`` is deliberately distinct from a passed check.  A
    # backend acknowledgement alone is not proof that the document changed.
    outcome: str = ""

    def __post_init__(self) -> None:
        if not self.outcome:
            self.outcome = "passed" if self.passed else "failed"

    @classmethod
    def not_verifiable(
        cls,
        verifier_name: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> "VerificationResult":
        return cls(
            verifier_name=verifier_name,
            passed=False,
            message=message,
            details=details or {},
            outcome="not_verifiable",
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize verification result to dictionary."""
        return {
            "verifier_name": self.verifier_name,
            "passed": self.passed,
            "message": self.message,
            "details": self.details,
            "violations": self.violations,
            "timestamp": self.timestamp,
            "outcome": self.outcome,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VerificationResult":
        return cls(
            verifier_name=data["verifier_name"],
            passed=bool(data.get("passed", False)),
            message=data.get("message", ""),
            details=dict(data.get("details", {})),
            violations=list(data.get("violations", [])),
            timestamp=float(data.get("timestamp", time.time())),
            outcome=data.get("outcome", ""),
        )
