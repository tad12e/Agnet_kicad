"""Base verifier interface."""

from __future__ import annotations

import abc
from typing import Any, Dict, Optional

from ..core.actions import Action
from ..core.results import ActionResult, VerificationResult


class BaseVerifier(abc.ABC):
    """Abstract base class for all domain verifiers."""

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Verifier identifier."""
        pass

    @abc.abstractmethod
    def verify(
        self,
        action: Action,
        result: ActionResult,
        expected: Optional[Dict[str, Any]] = None,
    ) -> VerificationResult:
        """Perform verification checks and return a structured VerificationResult."""
        pass
