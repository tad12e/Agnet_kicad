"""Agent verification coordinator."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..core.actions import Action, ActionType
from ..core.goals import Goal
from ..core.results import ActionResult, VerificationResult
from ..verification.base import BaseVerifier
from ..verification.connectivity import ConnectivityVerifier
from ..verification.drc import DRCVerifier
from ..verification.geometry import GeometryVerifier
from ..verification.intent import IntentVerifier
from ..verification.placement import PlacementVerifier
from ..verification.routing import RoutingVerifier
from ..verification.schematic_connectivity import SchematicConnectivityVerifier
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
            "schematic_connectivity": SchematicConnectivityVerifier(),
        }

    def verify_action(
        self,
        action: Action,
        result: ActionResult,
        expected: Optional[Dict[str, Any]] = None,
    ) -> VerificationResult:
        """Run relevant verifiers for an executed action."""
        if not result.success:
            return VerificationResult(
                verifier_name="agent_verifier",
                passed=False,
                message=f"Action execution failed: {result.error}",
            )

        from ..core.actions import ActionDomain

        t = action.action_type
        if action.domain == ActionDomain.SCHEMATIC and t in (
            ActionType.ADD_WIRE, ActionType.ADD_BUS, ActionType.ADD_JUNCTION,
            ActionType.ADD_LABEL, ActionType.VERIFY_CONNECTIVITY,
            ActionType.CHECK_CONNECTIVITY,
        ):
            return self.verifiers["schematic_connectivity"].verify(action, result, expected=expected)
        if t in (ActionType.ADD_FOOTPRINT, ActionType.MOVE_FOOTPRINT, ActionType.ROTATE_FOOTPRINT, ActionType.REMOVE_FOOTPRINT, ActionType.ADD_SYMBOL):
            return self.verifiers["placement"].verify(action, result, expected=expected)
        elif t in (ActionType.ADD_TRACK, ActionType.ROUTE_TRACK, ActionType.ADD_VIA, ActionType.ADD_WIRE):
            return self.verifiers["routing"].verify(action, result, expected=expected)
        elif t in (ActionType.RUN_DRC,):
            return self.verifiers["drc"].verify(action, result, expected=expected)
        elif t in (ActionType.VERIFY_CONNECTIVITY, ActionType.CHECK_CONNECTIVITY):
            return self.verifiers["connectivity"].verify(action, result, expected=expected)
        elif t in (ActionType.CHECK_GEOMETRY, ActionType.CREATE_BOARD_OUTLINE):
            return self.verifiers["geometry"].verify(action, result, expected=expected)
        else:
            return self.verifiers["structural"].verify(action, result, expected=expected)

    def verify_goal(self, goal: Goal, state: Dict[str, Any]) -> VerificationResult:
        """Verify if high-level goal criteria are satisfied."""
        intent_verifier: IntentVerifier = self.verifiers["intent"]  # type: ignore[assignment]
        return intent_verifier.verify_goal(goal, state)
