"""Explicit permission policy for actions crossing the runtime boundary."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .actions import Action, ActionType
from .contracts import PermissionDecision, PermissionRequest


DESTRUCTIVE_ACTIONS = frozenset(
    {
        ActionType.DELETE_SYMBOL,
        ActionType.REMOVE_FOOTPRINT,
        ActionType.DELETE_FOOTPRINT,
        ActionType.REMOVE_TRACK,
        ActionType.UNDO_ACTION,
        ActionType.LOAD_DOCUMENT,
        ActionType.LOAD_BOARD,
        ActionType.SAVE_DOCUMENT,
        ActionType.SAVE_BOARD,
        ActionType.CREATE_BOARD,
        ActionType.MODIFY_BOARD_OUTLINE,
    }
)

HIGH_RISK_ACTIONS = frozenset(
    {
        ActionType.ADD_TRACK,
        ActionType.ROUTE_TRACK,
        ActionType.ADD_VIA,
        ActionType.CREATE_ZONE,
        ActionType.ADD_ZONE,
        ActionType.FILL_ZONE,
        ActionType.CREATE_BOARD_OUTLINE,
    }
)


@dataclass(frozen=True)
class PermissionCheck:
    """Decision and optional approval request for one action."""

    decision: PermissionDecision
    request: Optional[PermissionRequest] = None


class PermissionPolicy:
    """Deterministic default-deny boundary for destructive operations.

    Ordinary inspection and design construction retain the existing behavior.
    Destructive and high-risk operations require an explicit approval, while
    callers may opt into stricter policies for all mutations.
    """

    def __init__(
        self,
        require_approval_for_high_risk: bool = True,
        require_approval_for_destructive: bool = True,
        require_approval_for_mutations: bool = False,
    ):
        self.require_approval_for_high_risk = require_approval_for_high_risk
        self.require_approval_for_destructive = require_approval_for_destructive
        self.require_approval_for_mutations = require_approval_for_mutations

    def risk_for(self, action: Action) -> str:
        if action.action_type in DESTRUCTIVE_ACTIONS:
            return "destructive"
        if action.action_type in HIGH_RISK_ACTIONS:
            return "high"
        if action.action_type.value.startswith(("add_", "move_", "rotate_", "modify_")):
            return "medium"
        return "low"

    def check(self, action: Action) -> PermissionCheck:
        risk = self.risk_for(action)
        needs_approval = (
            (risk == "destructive" and self.require_approval_for_destructive)
            or (risk == "high" and self.require_approval_for_high_risk)
            or (
                risk in {"medium", "high", "destructive"}
                and self.require_approval_for_mutations
            )
        )
        if not needs_approval:
            return PermissionCheck(PermissionDecision.ALLOW)
        request = PermissionRequest(
            action=action,
            reason=f"{risk.capitalize()} action requires explicit approval.",
            risk=risk,
        )
        return PermissionCheck(PermissionDecision.ASK, request)

    def decide(self, action: Action, approval: Optional[PermissionDecision] = None) -> PermissionCheck:
        check = self.check(action)
        if check.decision is not PermissionDecision.ASK or approval is None:
            return check
        if approval is PermissionDecision.ALLOW:
            return PermissionCheck(PermissionDecision.ALLOW, check.request)
        if approval is PermissionDecision.DENY:
            return PermissionCheck(PermissionDecision.DENY, check.request)
        return check
