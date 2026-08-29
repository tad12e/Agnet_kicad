"""High-level Schematic domain operations."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from ..core.actions import Action, ActionDomain, ActionType
from ..core.results import ActionResult
from ..backends.base import KiCadBackend
from .symbols import Component


class SchematicOperations:
    """High-level Schematic domain operations dispatcher."""

    def __init__(self, backend: KiCadBackend):
        self.backend = backend

    def add_symbol(
        self,
        lib_id: str,
        reference: str,
        value: str,
        x: float,
        y: float,
        rotation: float = 0,
    ) -> ActionResult:
        action = Action(
            action_type=ActionType.ADD_SYMBOL,
            domain=ActionDomain.SCHEMATIC,
            parameters={
                "lib_id": lib_id,
                "reference": reference,
                "value": value,
                "x": x,
                "y": y,
                "rotation": rotation,
            },
            description=f"Place symbol {reference} ({value}) at ({x}, {y})",
        )
        return self.backend.execute(action)

    def add_wire(
        self,
        start: Tuple[float, float],
        end: Tuple[float, float],
    ) -> ActionResult:
        action = Action(
            action_type=ActionType.ADD_WIRE,
            domain=ActionDomain.SCHEMATIC,
            parameters={"start": start, "end": end},
            description=f"Add wire {start} -> {end}",
        )
        return self.backend.execute(action)

    def add_junction(self, position: Tuple[float, float]) -> ActionResult:
        action = Action(
            action_type=ActionType.ADD_JUNCTION,
            domain=ActionDomain.SCHEMATIC,
            parameters={"position": position},
            description=f"Add junction at {position}",
        )
        return self.backend.execute(action)


class ComponentManager:
    """Manager for schematic components/symbols delegating to backend/operations."""

    def __init__(self, schematic: Any):
        self.schematic = schematic

    def add(
        self,
        lib_id: str,
        reference: str,
        value: str,
        position: Tuple[float, float],
        unit: int = 1,
        rotation: float = 0,
        item_id: Optional[str] = None,
    ) -> Component:
        res = self.schematic.operations.add_symbol(
            lib_id=lib_id,
            reference=reference,
            value=value,
            x=position[0],
            y=position[1],
            rotation=rotation,
        )
        item_uuid = res.data.get("uuid", item_id or "created-uuid")
        return Component(
            id=item_uuid,
            lib_id=lib_id,
            reference=reference,
            value=value,
            position_mm=position,
            unit=unit,
        )
