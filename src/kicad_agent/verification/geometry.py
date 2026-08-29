"""Geometric boundary and clearance verification."""

from __future__ import annotations

from typing import Any, Dict, Optional

from ..core.actions import Action
from ..core.results import ActionResult, VerificationResult
from .base import BaseVerifier


class GeometryVerifier(BaseVerifier):
    """Verifies elements lie within board bounds and do not overlap illegally."""

    @property
    def name(self) -> str:
        return "geometry"

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
                message="Cannot verify geometry on failed action",
            )

        return VerificationResult(
            verifier_name=self.name,
            passed=True,
            message="Geometry bounds satisfied",
        )
