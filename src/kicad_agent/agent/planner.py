"""Natural language request to structured Plan & Action IR converter."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from ..core.actions import Action, ActionDomain, ActionType
from ..core.goals import Goal, GoalType
from ..core.plans import Plan
from ..providers.llm import AnthropicProvider, LLMProvider


class Planner:
    """Translates user requests into domain-neutral structured plans."""

    def __init__(self, provider: Optional[LLMProvider] = None):
        self.provider = provider or AnthropicProvider()

    def plan_request(self, user_request: str, domain: str = "pcb") -> Plan:
        """Parse natural language request into structured goals and actions."""
        plan = Plan(metadata={"user_request": user_request, "domain": domain})

        # Rule-based / deterministic fallback parser for standard commands
        req_lower = user_request.lower()

        # Check for placement: "place resistor R1 (10k) at (100, 100)"
        m_place = re.search(r"place\s+(?:a\s+)?(\w+)?\s*([rcu]\d+)(?:\s*\(([^)]+)\))?\s*(?:at\s*\(?(\d+)[,\s]+(\d+)\)?)?", req_lower)
        if m_place:
            comp_type = m_place.group(1) or "resistor"
            ref = m_place.group(2).upper()
            val = m_place.group(3) or "10k"
            x = float(m_place.group(4)) if m_place.group(4) else 100.0
            y = float(m_place.group(5)) if m_place.group(5) else 100.0

            goal = Goal(
                goal_type=GoalType.PLACEMENT,
                description=f"Place {ref} at ({x}, {y})",
                targets=[ref],
                criteria={"x": x, "y": y},
            )
            plan.goals.append(goal)

            action = Action(
                action_type=ActionType.ADD_FOOTPRINT if domain == "pcb" else ActionType.ADD_SYMBOL,
                domain=ActionDomain.PCB if domain == "pcb" else ActionDomain.SCHEMATIC,
                parameters={
                    "reference": ref,
                    "value": val,
                    "x": x,
                    "y": y,
                    "component_type": comp_type,
                    "lib_id": f"Device:{ref[0]}",
                    "footprint_id": f"Resistor_SMD:R_0402",
                },
                description=f"Place {ref} at ({x}, {y})",
            )
            plan.add_action(action)
            return plan

        # Check for DRC check
        if "drc" in req_lower or "check" in req_lower:
            goal = Goal(goal_type=GoalType.DRC_CLEANUP, description="Run design rule check")
            plan.goals.append(goal)
            action = Action(action_type=ActionType.RUN_DRC, description="Run DRC")
            plan.add_action(action)
            return plan

        # Fallback inspection action
        action = Action(action_type=ActionType.GET_STATE, description="Inspect state")
        plan.add_action(action)
        return plan
