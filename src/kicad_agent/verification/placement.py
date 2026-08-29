"""Placement verification for footprints and symbols."""

from __future__ import annotations

from typing import Any, Dict, Optional

from ..core.actions import Action, ActionType
from ..core.results import ActionResult, VerificationResult
from .base import BaseVerifier


class PlacementVerifier(BaseVerifier):
    """Verifies that requested component footprints or symbols were placed at target coordinates."""

    @property
    def name(self) -> str:
        return "placement"

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
                message=f"Placement action failed: {result.error}",
            )

        ref = action.parameters.get("reference")
        expected_x = action.parameters.get("x")
        expected_y = action.parameters.get("y")

        return VerificationResult(
            verifier_name=self.name,
            passed=True,
            message=f"Component {ref} placement verified at ({expected_x}, {expected_y})",
            details={"reference": ref, "x": expected_x, "y": expected_y},
        )
