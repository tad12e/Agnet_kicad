"""Error analysis engine translating low-level exceptions to structured domain errors."""

from __future__ import annotations

from typing import Any, Dict, Optional

from ..core.errors import AgentError, ErrorCategory, ErrorSeverity


class ErrorAnalyzer:
    """Classifies raw exceptions and backend error strings into structured AgentErrors."""

    @staticmethod
    def analyze(exception: Exception, operation: Optional[str] = None, target: Optional[str] = None) -> AgentError:
        """Convert any exception or failure into a standardized AgentError."""
        if isinstance(exception, AgentError):
            return exception

        err_str = str(exception)

        if "already exists" in err_str.lower():
            return AgentError(
                category=ErrorCategory.PLACEMENT_ERROR,
                message=err_str,
                operation=operation,
                target_object=target,
                severity=ErrorSeverity.ERROR,
                recoverable=True,
            )
        elif "not found" in err_str.lower() or "does not exist" in err_str.lower():
            return AgentError(
                category=ErrorCategory.MISSING_OBJECT,
                message=err_str,
                operation=operation,
                target_object=target,
                severity=ErrorSeverity.ERROR,
                recoverable=True,
            )
        elif "connect" in err_str.lower() or "socket" in err_str.lower():
            return AgentError(
                category=ErrorCategory.CONNECTION_ERROR,
                message=err_str,
                operation=operation,
                severity=ErrorSeverity.CRITICAL,
                recoverable=False,
            )
        elif "drc" in err_str.lower() or "clearance" in err_str.lower():
            return AgentError(
                category=ErrorCategory.DRC_ERROR,
                message=err_str,
                operation=operation,
                severity=ErrorSeverity.WARNING,
                recoverable=True,
            )
        else:
            return AgentError(
                category=ErrorCategory.UNKNOWN_ERROR,
                message=err_str,
                operation=operation,
                target_object=target,
                severity=ErrorSeverity.ERROR,
                recoverable=True,
            )
