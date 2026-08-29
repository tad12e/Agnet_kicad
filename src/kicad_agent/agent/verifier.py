"""Agent verification coordinator."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..core.actions import Action
from ..core.goals import Goal
from ..core.results import ActionResult, VerificationResult
from ..verification.base import BaseVerifier
from ..verification.connectivity import ConnectivityVerifier
from ..verification.drc import DRCVerifier
from ..verification.geometry import GeometryVerifier
from ..verification.intent import IntentVerifier
from ..verification.placement import PlacementVerifier
from ..verification.routing import RoutingVerifier
from ..verification.structural import StructuralVerifier


class AgentVerifier:
    """Coordinates domain verifiers for action-level and goal-level checks."""

    def __init__(self):
        self.verifiers: Dict[str, BaseVerifier] = {
            "placement": PlacementVerifier(),
            "connectivity": ConnectivityVerifier(),
            "geometry": GeometryVerifier(),
            "routing": RoutingVerifier(),
            "drc": DRCVerifier(),
            "intent": IntentVerifier(),
            "structural": StructuralVerifier(),
        }

    def verify_action(self, action: Action, result: ActionResult) -> VerificationResult:
        """Run relevant verifiers for an executed action."""
        if not result.success:
            return VerificationResult(
                verifier_name="agent_verifier",
                passed=False,
                message=f"Action failed: {result.error}",
            )

        if "placement" in action.action_type.value:
            return self.verifiers["placement"].verify(action, result)
        elif "track" in action.action_type.value or "via" in action.action_type.value:
            return self.verifiers["routing"].verify(action, result)
        elif "drc" in action.action_type.value:
            return self.verifiers["drc"].verify(action, result)
        else:
            return self.verifiers["structural"].verify(action, result)

    def verify_goal(self, goal: Goal, state: Dict[str, Any]) -> VerificationResult:
        """Verify if high-level goal criteria are satisfied."""
        intent_verifier: IntentVerifier = self.verifiers["intent"]  # type: ignore[assignment]
        return intent_verifier.verify_goal(goal, state)
