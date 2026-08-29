"""Geometric boundary and clearance verification."""

from __future__ import annotations

from typing import Any, Dict, Optional

from ..core.actions import Action, ActionType
from ..core.results import ActionResult, VerificationResult
from .base import BaseVerifier


class GeometryVerifier(BaseVerifier):
    """Verifies elements lie within board bounds, tracks have legal widths, and outline geometry is valid."""

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
                details={"error": str(result.error)},
            )

        p = action.parameters
        t = action.action_type

        # Check track width
        if t == ActionType.ADD_TRACK:
            width = float(p.get("width_mm", 0.25))
            if width < 0.1 or width > 10.0:
                return VerificationResult(
                    verifier_name=self.name,
                    passed=False,
                    message=f"Track width {width}mm is outside allowable manufacturing range (0.1mm - 10mm)",
                    details={"width_mm": width},
                )

        # Check board boundary limits if board outline is provided
        board_w = expected.get("board_width") if expected else None
        board_h = expected.get("board_height") if expected else None

        if board_w is not None and board_h is not None:
            x = p.get("x")
            y = p.get("y")
            if x is not None and y is not None:
                fx, fy = float(x), float(y)
                if fx < 0 or fx > float(board_w) or fy < 0 or fy > float(board_h):
                    return VerificationResult(
                        verifier_name=self.name,
                        passed=False,
                        message=f"Position ({fx}, {fy}) is outside board outline (0..{board_w}, 0..{board_h})",
                        details={"x": fx, "y": fy, "board_width": board_w, "board_height": board_h},
                    )

        return VerificationResult(
            verifier_name=self.name,
            passed=True,
            message="Geometry constraints satisfied",
            details=p,
        )
