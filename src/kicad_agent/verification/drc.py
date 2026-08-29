"""Design Rule Check (DRC) verification."""

from __future__ import annotations

from typing import Any, Dict, Optional

from ..core.actions import Action
from ..core.results import ActionResult, VerificationResult
from .base import BaseVerifier


class DRCVerifier(BaseVerifier):
    """Verifies KiCad Design Rule Check outputs."""

    @property
    def name(self) -> str:
        return "drc"

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
                message=f"DRC execution failed: {result.error}",
            )

        status = result.data.get("status", "clean")
        unconnected = result.data.get("unconnected_count", 0)

        passed = status == "clean" and unconnected == 0
        return VerificationResult(
            verifier_name=self.name,
            passed=passed,
            message=f"DRC status: {status}, unconnected: {unconnected}",
            details=result.data,
        )
