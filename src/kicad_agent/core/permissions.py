"""Permission and risk policy for model-selected tools."""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Dict


class ToolRisk(str, enum.Enum):
    READ = "read"
    LOW = "low"
    HIGH = "high"
    CRITICAL = "critical"


class PermissionDecision(str, enum.Enum):
    ALLOW = "allow"
    ASK = "ask"
    DENY = "deny"


@dataclass(frozen=True)
class PermissionPolicy:
    """Deterministic default policy applied before backend mutation."""

    ask_above: ToolRisk = ToolRisk.HIGH
    deny_critical: bool = True

    def decide(self, risk: ToolRisk) -> PermissionDecision:
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
