"""Agent verification coordinator for two-level (Action & Goal) verification."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..core.actions import Action, ActionType
from ..core.goals import Goal
from ..core.results import ActionResult, VerificationResult
from ..tasks.task import Task
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
    """Coordinates domain verifiers for action-level and goal/task-level checks."""

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
        """Run action-level verifier for an individual executed operation."""
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
        elif t in (ActionType.RUN_DRC, ActionType.RUN_ERC):
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

    def verify_task(self, task: Task, state: Dict[str, Any]) -> VerificationResult:
        """Perform comprehensive goal-level verification of overall engineering task requirements."""
        components = state.get("components", [])
        existing_refs = set()
        for c in components:
            if isinstance(c, dict):
                existing_refs.add(c.get("ref", c.get("reference", "")))
            elif isinstance(c, str):
                existing_refs.add(c)

        req_components = task.requirements.get("components", [])
        missing = []
        for req_c in req_components:
            expected_ref = req_c.get("reference")
            if expected_ref and expected_ref not in existing_refs:
                missing.append(expected_ref)

        if missing:
            return VerificationResult(
                verifier_name="task_verifier",
                passed=False,
                message=f"Goal verification failed: Missing required components: {', '.join(missing)}",
                violations=[{"type": "missing_component", "reference": ref} for ref in missing],
            )

        # Check for unconnected violations if reported
        unconnected = state.get("unconnected_pads", 0)
        if isinstance(unconnected, int) and unconnected > 0 and task.requirements.get("require_all_routed", False):
            return VerificationResult(
                verifier_name="task_verifier",
                passed=False,
                message=f"Goal verification failed: Design has {unconnected} unconnected nets.",
            )

        return VerificationResult(
            verifier_name="task_verifier",
            passed=True,
            message=f"All engineering criteria verified for task '{task.task_type.value}'",
            details={"components_count": len(components)},
        )
