"""Connectivity verification for nets and ratsnest."""

from __future__ import annotations

from typing import Any, Dict, Optional

from ..core.actions import Action
from ..core.results import ActionResult, VerificationResult
from .base import BaseVerifier


class ConnectivityVerifier(BaseVerifier):
    """Verifies electrical net connectivity and unrouted pad counts."""

    @property
    def name(self) -> str:
        return "connectivity"

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
                message="Cannot verify connectivity on failed action",
            )

        unconnected = result.data.get("unconnected_pads", result.data.get("unconnected_count", 0))
        max_allowed = expected.get("max_unconnected", 0) if expected else 0

        passed = unconnected <= max_allowed
        return VerificationResult(
            verifier_name=self.name,
            passed=passed,
            message=f"Unconnected pad count is {unconnected} (threshold: {max_allowed})",
            details={"unconnected": unconnected},
        )
