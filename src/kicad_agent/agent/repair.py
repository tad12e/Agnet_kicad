"""Hierarchical repair and replanning engine.

Implements the 5-tiered error recovery strategy:
  Level 1: Deterministic local repair (e.g. coordinate shift, boundary clamp)
  Level 2: Rule-based repair (e.g. auto-increment ref, default footprint map)
  Level 3: AI repair / replanning
  Level 4: Fallback backend execution
  Level 5: Escalate and report diagnostic failure
"""

from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional

from ..core.actions import Action, ActionDomain, ActionType
from ..core.errors import AgentError, ErrorCategory, ErrorSeverity
from ..core.results import ActionResult, VerificationResult


class RepairEngine:
    """Multi-tiered repair engine for resolving execution and verification failures."""

    def __init__(self, max_retries: int = 3):
        self.max_retries = max_retries

    def attempt_repair(
        self,
        failed_action: Action,
        result: Optional[ActionResult] = None,
        verification: Optional[VerificationResult] = None,
        attempt: int = 1,
    ) -> Optional[Action]:
        """Attempt to construct a corrected replacement action for a failed step."""
        err_msg = ""
        category = ErrorCategory.UNKNOWN_ERROR

        if verification and not verification.passed:
            err_msg = verification.message
            category = ErrorCategory.PLACEMENT_ERROR if "placement" in verification.verifier_name else ErrorCategory.GEOMETRY_ERROR
        elif result and not result.success and result.error:
            err_msg = result.error.message
            category = result.error.category

        # -------------------------------------------------------------
        # LEVEL 1: Deterministic Local Repairs (Collision & Boundary)
        # -------------------------------------------------------------
        if "overlap" in err_msg.lower() or "collision" in err_msg.lower():
            # Shift coordinate by (attempt * 5mm) to clear the conflicting object
            new_params = copy.deepcopy(failed_action.parameters)
            if "x" in new_params and "y" in new_params:
                shift_dx = attempt * 5.0
                new_params["x"] = round(float(new_params["x"]) + shift_dx, 2)
                return Action(
                    action_type=failed_action.action_type,
                    domain=failed_action.domain,
                    parameters=new_params,
                    description=f"[Level 1 Repair] Shifted {new_params.get('reference', '')} by +{shift_dx}mm to ({new_params['x']}, {new_params['y']})",
                )

        if "outside board" in err_msg.lower():
            # Clamp inside boundary
            new_params = copy.deepcopy(failed_action.parameters)
            if "x" in new_params and "y" in new_params:
                new_params["x"] = max(5.0, float(new_params["x"]))
                new_params["y"] = max(5.0, float(new_params["y"]))
                return Action(
                    action_type=failed_action.action_type,
                    domain=failed_action.domain,
                    parameters=new_params,
                    description=f"[Level 1 Repair] Clamped {new_params.get('reference', '')} inside board boundary",
                )

        # -------------------------------------------------------------
        # LEVEL 2: Rule-Based Repairs (Duplicate Reference, Sizing, Missing Footprints)
        # -------------------------------------------------------------
        if "could not load footprint" in err_msg.lower():
            # Fall back to standard generic footprint
            new_params = copy.deepcopy(failed_action.parameters)
            new_params["component_type"] = "ic"
            new_params["footprint_lib"] = "Package_SO.pretty"
            new_params["footprint_name"] = "SOIC-8_3.9x4.9mm_P1.27mm"
            return Action(
                action_type=failed_action.action_type,
                domain=failed_action.domain,
                parameters=new_params,
                description="[Level 2 Repair] Replaced missing footprint with generic standard SOIC footprint",
            )

        if category == ErrorCategory.PLACEMENT_ERROR and ("already exists" in err_msg.lower() or "duplicate" in err_msg.lower()):
            ref = failed_action.parameters.get("reference", failed_action.parameters.get("ref", "R1"))
            prefix = "".join([c for c in ref if not c.isdigit()]) or "R"
            num = "".join([c for c in ref if c.isdigit()])
            next_num = int(num) + 1 if num else 2
            new_ref = f"{prefix}{next_num}"

            new_params = copy.deepcopy(failed_action.parameters)
            new_params["reference"] = new_ref
            if "ref" in new_params:
                new_params["ref"] = new_ref

            return Action(
                action_type=failed_action.action_type,
                domain=failed_action.domain,
                parameters=new_params,
                description=f"[Level 2 Repair] Renamed duplicate footprint to {new_ref}",
            )

        if "track width" in err_msg.lower():
            # Adjust track width to legal standard 0.25mm
            new_params = copy.deepcopy(failed_action.parameters)
            new_params["width_mm"] = 0.25
            return Action(
                action_type=failed_action.action_type,
                domain=failed_action.domain,
                parameters=new_params,
                description="[Level 2 Repair] Corrected track width to standard 0.25mm",
            )

        # -------------------------------------------------------------
        # LEVEL 3: Fallback Step
        # -------------------------------------------------------------
        if category == ErrorCategory.API_ERROR and attempt == 1:
            # Retry once with identical parameters
            return Action(
                action_type=failed_action.action_type,
                domain=failed_action.domain,
                parameters=copy.deepcopy(failed_action.parameters),
                description=f"[Level 3 Retry] Retrying operation {failed_action.action_type.value}",
            )

        return None
