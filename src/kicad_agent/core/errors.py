"""Structured error representation for KiCad AI Agent.

Normalizes low-level backend, IPC, syntax, and verification failures
into structured, typed errors suitable for AI analysis, automated repair,
and developer reporting.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


class ErrorSeverity(str, enum.Enum):
    """Severity classification of an agent error."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ErrorCategory(str, enum.Enum):
    """Standardized error categories for domain analysis and repair."""
    INVALID_ACTION = "INVALID_ACTION"
    INVALID_PARAMETER = "INVALID_PARAMETER"
    MISSING_OBJECT = "MISSING_OBJECT"
    
    # Transport & API errors
    IPC_ERROR = "IPC_ERROR"
    API_ERROR = "API_ERROR"
    CONNECTION_ERROR = "CONNECTION_ERROR"
    
    # PCB Domain errors
    PLACEMENT_ERROR = "PLACEMENT_ERROR"
    GEOMETRY_ERROR = "GEOMETRY_ERROR"
    CONNECTIVITY_ERROR = "CONNECTIVITY_ERROR"
    ROUTING_ERROR = "ROUTING_ERROR"
    DRC_ERROR = "DRC_ERROR"
    
    # Schematic Domain errors
    SYMBOL_NOT_FOUND = "SYMBOL_NOT_FOUND"
    PIN_NOT_FOUND = "PIN_NOT_FOUND"
    SCHEMATIC_CONNECTIVITY_ERROR = "SCHEMATIC_CONNECTIVITY_ERROR"
    
    # File & Environment errors
    FILE_ERROR = "FILE_ERROR"
    VERSION_ERROR = "VERSION_ERROR"
    
    # Generic / Unclassified
    UNKNOWN_ERROR = "UNKNOWN_ERROR"


@dataclass
class AgentError(Exception):
    """Structured domain error representation.
    
    Attributes:
        category: Standard category code.
        message: Human-readable explanation.
        error_id: Unique error identifier.
        severity: Error severity level.
        operation: The action/operation being attempted when error occurred.
        target_object: The reference designator, net, or element involved.
        context: Additional diagnostic metadata, coordinates, or stack trace snippets.
        recoverable: Whether the repair engine can attempt automatic remediation.
    """
    category: ErrorCategory = ErrorCategory.UNKNOWN_ERROR
    message: str = ""
    error_id: str = ""
    severity: ErrorSeverity = ErrorSeverity.ERROR
    operation: Optional[str] = None
    target_object: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)
    recoverable: bool = True

    def __str__(self) -> str:
        obj_str = f" [target={self.target_object}]" if self.target_object else ""
        op_str = f" during {self.operation}" if self.operation else ""
        return f"[{self.category.value}]{op_str}{obj_str}: {self.message}"

    def to_dict(self) -> Dict[str, Any]:
        """Serialize error to dictionary."""
        return {
            "error_id": self.error_id,
            "category": self.category.value,
            "severity": self.severity.value,
            "message": self.message,
            "operation": self.operation,
            "target_object": self.target_object,
            "context": self.context,
            "recoverable": self.recoverable,
        }
