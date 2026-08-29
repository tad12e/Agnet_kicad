"""Natural language request to structured Plan & Action IR converter."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from ..core.actions import Action, ActionDomain, ActionType
from ..core.goals import Goal, GoalType
from ..core.plans import Plan
from ..providers.llm import AnthropicProvider, LLMProvider


class Planner:
    """Translates user requests into domain-neutral structured plans with dependency graphs."""

    def __init__(self, provider: Optional[LLMProvider] = None):
        self.provider = provider or AnthropicProvider()

    def plan_request(self, user_request: str, domain: str = "pcb", current_state: Optional[Dict[str, Any]] = None) -> Plan:
        """Parse natural language request into structured goals and actions."""
        plan = Plan(metadata={"user_request": user_request, "domain": domain})
        req_lower = user_request.lower()

        # 1. Multi-component Board Creation: "create a pcb with arduino leonardo, led, resistor and connector"
        if "create" in req_lower and "pcb" in req_lower:
            plan.goals.append(Goal(goal_type=GoalType.PLACEMENT, description="Create PCB and place requested components"))
            
            # Step 1: Create board
            act_board = Action(
                action_type=ActionType.CREATE_BOARD,
                domain=ActionDomain.PCB,
                description="Initialize blank PCB",
            )
            plan.add_action(act_board)

            # Step 2: Board outline
            act_outline = Action(
                action_type=ActionType.CREATE_BOARD_OUTLINE,
                domain=ActionDomain.PCB,
                parameters={"width": 80.0, "height": 50.0},
                description="Create 80x50mm board outline",
            )
            plan.add_action(act_outline)

            # Check for specific items mentioned
            pos_x = 20.0
            if "arduino" in req_lower or "leonardo" in req_lower or "microcontroller" in req_lower:
                act_mcu = Action(
                    action_type=ActionType.ADD_FOOTPRINT,
                    domain=ActionDomain.PCB,
                    parameters={"reference": "U1", "library": "Module:Arduino_Leonardo", "x": 40.0, "y": 25.0, "value": "ATmega32U4"},
                    description="Place Arduino Leonardo microcontroller U1",
                )
                plan.add_action(act_mcu)

            if "resistor" in req_lower or "r1" in req_lower:
                act_r = Action(
                    action_type=ActionType.ADD_FOOTPRINT,
                    domain=ActionDomain.PCB,
                    parameters={"reference": "R1", "component_type": "resistor", "x": 20.0, "y": 15.0, "value": "10k"},
                    description="Place resistor R1",
                )
                plan.add_action(act_r)

            if "led" in req_lower:
                act_led = Action(
                    action_type=ActionType.ADD_FOOTPRINT,
                    domain=ActionDomain.PCB,
                    parameters={"reference": "D1", "component_type": "led", "x": 20.0, "y": 25.0, "value": "RED"},
                    description="Place LED D1",
                )
                plan.add_action(act_led)

            if "connector" in req_lower or "header" in req_lower:
                act_conn = Action(
                    action_type=ActionType.ADD_FOOTPRINT,
                    domain=ActionDomain.PCB,
                    parameters={"reference": "J1", "library": "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical", "x": 10.0, "y": 25.0, "value": "Power"},
                    description="Place power connector J1",
                )
                plan.add_action(act_conn)

            return plan

        # 2. Move Footprint: "move R1 to (30, 20)" or "move R1 to 30,20"
        m_move = re.search(r"move\s+([a-zA-Z]+\d+)\s+(?:to\s+)?\(?([0-9.]+)[,\s]+([0-9.]+)\)?", req_lower)
        if m_move:
            ref = m_move.group(1).upper()
            x = float(m_move.group(2))
            y = float(m_move.group(3))

            goal = Goal(
                goal_type=GoalType.PLACEMENT,
                description=f"Move {ref} to ({x}, {y})",
                targets=[ref],
                criteria={"x": x, "y": y},
            )
            plan.goals.append(goal)

            action = Action(
                action_type=ActionType.MOVE_FOOTPRINT,
                domain=ActionDomain.PCB,
                parameters={"reference": ref, "x": x, "y": y},
                preconditions=[f"{ref} exists", "target coordinates valid"],
                description=f"Move footprint {ref} to ({x}, {y})",
            )
            plan.add_action(action)
            return plan

        # 3. Rotate Footprint: "rotate R1 by 90 degrees" or "rotate R1 90"
        m_rotate = re.search(r"rotate\s+([a-zA-Z]+\d+)\s+(?:by\s+)?([0-9.]+)(?:\s*deg)?", req_lower)
        if m_rotate:
            ref = m_rotate.group(1).upper()
            angle = float(m_rotate.group(2))

            goal = Goal(
                goal_type=GoalType.PLACEMENT,
                description=f"Rotate {ref} by {angle} degrees",
                targets=[ref],
            )
            plan.goals.append(goal)

            action = Action(
                action_type=ActionType.ROTATE_FOOTPRINT,
                domain=ActionDomain.PCB,
                parameters={"reference": ref, "angle": angle},
                preconditions=[f"{ref} exists"],
                description=f"Rotate footprint {ref} by {angle} deg",
            )
            plan.add_action(action)
            return plan

        # 4. Remove / Delete Footprint: "remove R1" or "delete footprint R1"
        m_delete = re.search(r"(?:delete|remove)\s+(?:footprint\s+)?([a-zA-Z]+\d+)", req_lower)
        if m_delete:
            ref = m_delete.group(1).upper()
            action = Action(
                action_type=ActionType.REMOVE_FOOTPRINT,
                domain=ActionDomain.PCB,
                parameters={"reference": ref},
                preconditions=[f"{ref} exists"],
                description=f"Remove footprint {ref}",
            )
            plan.add_action(action)
            return plan

        # 5. Place single component: "place resistor R1 (10k) at (100, 100)"
        m_place = re.search(r"place\s+(?:a\s+)?(\w+)?\s*([a-zA-Z]+\d+)(?:\s*\(([^)]+)\))?\s*(?:at\s*\(?([0-9.]+)[,\s]+([0-9.]+)\)?)?", req_lower)
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

        # 6. Board Outline: "create board outline 80x50"
        m_outline = re.search(r"outline\s+([0-9.]+)\s*[xX*]\s*([0-9.]+)", req_lower)
        if m_outline:
            w = float(m_outline.group(1))
            h = float(m_outline.group(2))
            action = Action(
                action_type=ActionType.CREATE_BOARD_OUTLINE,
                domain=ActionDomain.PCB,
                parameters={"width": w, "height": h},
                description=f"Create board outline {w}x{h} mm",
            )
            plan.add_action(action)
            return plan

        # 7. Check / DRC
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
