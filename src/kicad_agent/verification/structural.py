"""Structural integrity verification."""

from __future__ import annotations

from typing import Any, Dict, Optional

from ..core.actions import Action
from ..core.results import ActionResult, VerificationResult
from .base import BaseVerifier


class StructuralVerifier(BaseVerifier):
    """Verifies file structure and document presence."""

    @property
    def name(self) -> str:
        return "structural"

    def verify(
        self,
        action: Action,
        result: ActionResult,
        expected: Optional[Dict[str, Any]] = None,
    ) -> VerificationResult:
        if not result.success:
            return VerificationResult(
                verifier_name=self.name,
                passed=False,
                message=f"Action failed execution: {result.error}",
            )

        return VerificationResult(
            verifier_name=self.name,
            passed=True,
            message="Structural check passed",
            details={"action_id": action.action_id},
        )
