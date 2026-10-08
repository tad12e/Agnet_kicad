"""Permission and risk policy for model-selected tools."""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Any, Dict, Optional, Union

from .actions import Action, ActionType
from .contracts import PermissionDecision, PermissionRequest


class ToolRisk(str, enum.Enum):
    READ = "read"
    LOW = "low"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class PermissionPolicy:
    """Deterministic default policy applied before backend mutation."""

    ask_above: ToolRisk = ToolRisk.HIGH
    deny_critical: bool = True

    def decide(
        self,
        target: Union[ToolRisk, Action],
        approval: Optional[PermissionDecision] = None,
    ) -> Union[PermissionDecision, "PermissionResult"]:
        if isinstance(target, Action):
            risk = self._action_risk(target)
            decision = self.decide(risk)
            if approval is not None:
                decision = approval
            request = None
            if decision is not PermissionDecision.ALLOW:
                request = PermissionRequest(
                    action=target,
                    reason=f"Action '{target.action_type.value}' requires permission.",
                    risk="destructive" if risk is ToolRisk.HIGH else risk.value,
                    decision=decision,
                )
            return PermissionResult(decision=decision, request=request)
        risk = target
        if risk is ToolRisk.CRITICAL and self.deny_critical:
            return PermissionDecision.DENY
        order = {
            ToolRisk.READ: 0,
            ToolRisk.LOW: 1,
            ToolRisk.HIGH: 2,
            ToolRisk.CRITICAL: 3,
        }
        if order[risk] >= order[self.ask_above]:
            return PermissionDecision.ASK
        return PermissionDecision.ALLOW

    @staticmethod
    def _action_risk(action: Action) -> ToolRisk:
        if action.action_type in {
            ActionType.DELETE_SYMBOL,
            ActionType.REMOVE_FOOTPRINT,
            ActionType.DELETE_FOOTPRINT,
        }:
            return ToolRisk.HIGH
        if action.action_type is ActionType.CREATE_BOARD:
            return ToolRisk.CRITICAL
        return ToolRisk.LOW

    def check(self, action: Action) -> "PermissionResult":
        """Return the structured action-level permission result."""
        return self.decide(action)


@dataclass(frozen=True)
class PermissionResult:
    decision: PermissionDecision
    request: Optional[PermissionRequest]


TOOL_RISKS: Dict[str, ToolRisk] = {
    "remove_footprint": ToolRisk.HIGH,
    "delete_symbol": ToolRisk.HIGH,
    "add_track": ToolRisk.HIGH,
    "add_via": ToolRisk.HIGH,
    "create_zone": ToolRisk.HIGH,
    "load_board": ToolRisk.HIGH,
    "save_board": ToolRisk.HIGH,
    "create_board": ToolRisk.CRITICAL,
    "read": ToolRisk.READ,
}
