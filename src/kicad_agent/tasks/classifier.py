"""Deterministic natural-language task classification for the agent runtime."""

from __future__ import annotations

import re
import time
from typing import Any, Dict

from .task import Task, TaskType


class TaskClassifier:
    """Convert common KiCad requests into validated structured tasks."""

    def classify(self, user_request: str, domain: str = "pcb") -> Task:
        request = user_request.strip()
        lowered = request.lower()
        task_type = TaskType.CUSTOM

        if any(w in lowered for w in ("build", "create", "design", "make")) and any(
            word in lowered for word in ("circuit", "schematic", "pcb", "regulator", "supply", "filter", "divider")
        ):
            task_type = TaskType.BUILD_CIRCUIT
        elif "create" in lowered and ("schematic" in lowered or "pcb" in lowered):
            task_type = (
                TaskType.CREATE_SCHEMATIC
                if domain == "schematic"
                else TaskType.CREATE_PCB
            )
        elif "route" in lowered and "board" in lowered:
            task_type = TaskType.ROUTE_BOARD
        elif "drc" in lowered or "error" in lowered:
            task_type = TaskType.FIX_DRC_ERRORS

        requirements: Dict[str, Any] = {"circuit_type": "generic"}
        if "7805" in lowered or "regulator" in lowered or "power supply" in lowered:
            requirements["circuit_type"] = "power_supply"
            requirements["components"] = [
                {"type": "regulator", "reference": "U1", "value": "LM7805"},
                {"type": "capacitor", "reference": "C1", "value": "0.33uF"},
                {"type": "capacitor", "reference": "C2", "value": "0.1uF"},
                {"type": "resistor", "reference": "R1", "value": "1k"},
                {"type": "led", "reference": "D1", "value": "GREEN"},
            ]
        elif "divider" in lowered:
            requirements["circuit_type"] = "voltage_divider"
            requirements["components"] = [
                {"type": "resistor", "reference": "R1", "value": "10k"},
                {"type": "resistor", "reference": "R2", "value": "4.7k"},
            ]
        elif "filter" in lowered:
            requirements["circuit_type"] = "rc_filter"
            requirements["components"] = [
                {"type": "resistor", "reference": "R1", "value": "1k"},
                {"type": "capacitor", "reference": "C1", "value": "100nF"},
            ]
        elif "arduino" in lowered or "mcu" in lowered or "microcontroller" in lowered:
            requirements["circuit_type"] = "microcontroller"
            requirements["components"] = [
                {"type": "microcontroller", "reference": "U1", "value": "ATmega32U4"},
                {"type": "led", "reference": "D1", "value": "LED"},
                {"type": "resistor", "reference": "R1", "value": "1k"},
                {"type": "capacitor", "reference": "C1", "value": "100nF"},
            ]
        elif "led" in lowered:
            requirements["circuit_type"] = "led"
            requirements["components"] = [
                {"type": "led", "reference": "D1", "value": "RED"},
                {"type": "resistor", "reference": "R1", "value": "330R"},
            ]

        return Task(
            task_id=f"task-{int(time.time() * 1000)}",
            task_type=task_type,
            domain=domain,
            description=request,
            requirements=requirements,
            constraints={"domain": domain},
        )
