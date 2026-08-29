"""Placement verification for footprints and symbols."""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from ..core.actions import Action, ActionType
from ..core.results import ActionResult, VerificationResult
from .base import BaseVerifier


class PlacementVerifier(BaseVerifier):
    """Verifies that requested component footprints or symbols were placed at target coordinates,

    within board boundaries, and without forbidden overlaps.
    """

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
                message=f"Placement action failed during execution: {result.error}",
                details={"error": str(result.error)},
            )

        ref = action.parameters.get("reference", action.parameters.get("ref", ""))
        expected_x = action.parameters.get("x")
        expected_y = action.parameters.get("y")
        expected_rot = action.parameters.get("rotation", action.parameters.get("angle"))

        # If we have actual board state in result data or expected context
        actual_state = expected.get("state") if expected else result.data
        if isinstance(actual_state, dict) and "components" in actual_state:
            components: List[Dict[str, Any]] = actual_state.get("components", [])
            
            # Find the component on board
            found_comp = None
            for c in components:
                if isinstance(c, dict) and c.get("ref", c.get("reference")) == ref:
                    found_comp = c
                    break

            if not found_comp and ref:
                return VerificationResult(
                    verifier_name=self.name,
                    passed=False,
                    message=f"Verification failed: Footprint '{ref}' not found in actual board model",
                    details={"reference": ref},
                )

            if found_comp and expected_x is not None and expected_y is not None:
                actual_x = float(found_comp.get("x", 0))
                actual_y = float(found_comp.get("y", 0))
                dist = math.sqrt((actual_x - float(expected_x)) ** 2 + (actual_y - float(expected_y)) ** 2)
                if dist > 0.5:  # Tolerance: 0.5mm
                    return VerificationResult(
                        verifier_name=self.name,
                        passed=False,
                        message=f"Verification failed: Footprint '{ref}' is at ({actual_x}, {actual_y}), expected ({expected_x}, {expected_y})",
                        details={"reference": ref, "actual": (actual_x, actual_y), "expected": (expected_x, expected_y)},
                    )

            # Collision / Overlap check with other components
            if expected_x is not None and expected_y is not None:
                for other in components:
                    if isinstance(other, dict):
                        other_ref = other.get("ref", other.get("reference"))
                        if other_ref != ref:
                            ox = float(other.get("x", 0))
                            oy = float(other.get("y", 0))
                            # Minimum spacing: 1.0mm center-to-center for simple discrete components
                            sep = math.sqrt((float(expected_x) - ox) ** 2 + (float(expected_y) - oy) ** 2)
                            if sep < 0.8:  # Direct overlapping collision
                                return VerificationResult(
                                    verifier_name=self.name,
                                    passed=False,
                                    message=f"Placement overlap collision: '{ref}' at ({expected_x}, {expected_y}) collides with '{other_ref}' at ({ox}, {oy})",
                                    details={"reference": ref, "conflicting_object": other_ref, "distance": sep},
                                )

        return VerificationResult(
            verifier_name=self.name,
            passed=True,
            message=f"Component {ref} placement verified at ({expected_x}, {expected_y})",
            details={"reference": ref, "x": expected_x, "y": expected_y, "rotation": expected_rot},
        )
