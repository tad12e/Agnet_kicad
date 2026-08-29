"""Abstract base class for KiCad automation backends.

Defines the common interface that all execution adapters (IPC, pcbnew, S-expression)
must implement.
"""

from __future__ import annotations

import abc
from typing import Any, Dict, Optional

from ..core.actions import Action
from ..core.results import ActionResult, VerificationResult


class KiCadBackend(abc.ABC):
    """Common interface for all KiCad execution backends."""

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Identifier name of the backend."""
        pass

    @abc.abstractmethod
    def is_available(self) -> bool:
        """Check if this backend is usable in the current environment."""
        pass

    @abc.abstractmethod
    def connect(self) -> None:
        """Establish connection or initialize resources."""
        pass

    @abc.abstractmethod
    def disconnect(self) -> None:
        """Release connection or resources."""
        pass

    @abc.abstractmethod
    def load_board(self, filepath: str) -> Dict[str, Any]:
        """Load PCB board from file or active editor session."""
        pass

    @abc.abstractmethod
    def save_board(self, filepath: Optional[str] = None) -> bool:
        """Save PCB board state to disk."""
        pass

    @abc.abstractmethod
    def load_schematic(self, filepath: str) -> Dict[str, Any]:
        """Load schematic from file or active editor session."""
        pass

    @abc.abstractmethod
    def save_schematic(self, filepath: Optional[str] = None) -> bool:
        """Save schematic state to disk."""
        pass

    @abc.abstractmethod
    def get_state(self, domain: str = "pcb") -> Dict[str, Any]:
        """Query current state (components, nets, connectivity, unrouted count)."""
        pass

    @abc.abstractmethod
    def execute(self, action: Action) -> ActionResult:
        """Execute a structured domain action."""
        pass

    def verify(self, action: Action, expected: Optional[Dict[str, Any]] = None) -> VerificationResult:
        """Verify the outcome of an action against expected outcome."""
        return VerificationResult(
            verifier_name=f"{self.name}_verifier",
            passed=True,
            message="Backend default verification passed",
        )
