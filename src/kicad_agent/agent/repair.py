"""Tiered repair and replanning engine."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..core.actions import Action, ActionType
from ..core.errors import AgentError, ErrorCategory
from ..core.plans import Plan
from ..core.results import ActionResult, VerificationResult


class RepairEngine:
    """Multi-tiered repair engine: local deterministic -> rule-based -> fallback."""

    def attempt_repair(
        self,
        failed_action: Action,
        result: ActionResult,
        verification: Optional[VerificationResult] = None,
    ) -> Optional[Action]:
        """Attempt to construct a corrected replacement action for a failed step."""
        err = result.error
        if not err:
            return None

        # Rule 1: Duplicate reference -> increment index
        if err.category == ErrorCategory.PLACEMENT_ERROR and "already exists" in err.message.lower():
            ref = failed_action.parameters.get("reference", "R1")
            prefix = "".join([c for c in ref if not c.isdigit()])
            num = "".join([c for c in ref if c.isdigit()])
            next_num = int(num) + 1 if num else 2
            new_ref = f"{prefix}{next_num}"

            new_params = dict(failed_action.parameters)
            new_params["reference"] = new_ref

            return Action(
                action_type=failed_action.action_type,
                domain=failed_action.domain,
                parameters=new_params,
                description=f"Repaired: place {new_ref} instead of {ref}",
            )

        # Rule 2: Overlapping position -> shift position slightly
        if err.category == ErrorCategory.GEOMETRY_ERROR or err.category == ErrorCategory.DRC_ERROR:
            new_params = dict(failed_action.parameters)
            if "x" in new_params and "y" in new_params:
                new_params["x"] = new_params["x"] + 10.0
                return Action(
                    action_type=failed_action.action_type,
                    domain=failed_action.domain,
                    parameters=new_params,
                    description=f"Repaired: shifted coordinate to ({new_params['x']}, {new_params['y']})",
                )

        return None
