"""High-level PCB domain operations."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from ..core.actions import Action, ActionType
from ..core.results import ActionResult
from ..backends.base import KiCadBackend


class PCBOperations:
    """High-level PCB domain operations builder and dispatcher."""

    def __init__(self, backend: KiCadBackend):
        self.backend = backend

    def place_footprint(
        self,
        footprint_id: str,
        reference: str,
        value: str,
        x: float,
        y: float,
        layer: str = "F.Cu",
        rotation: float = 0,
    ) -> ActionResult:
        action = Action(
            action_type=ActionType.ADD_FOOTPRINT,
            parameters={
                "footprint_id": footprint_id,
                "reference": reference,
                "value": value,
                "x": x,
                "y": y,
                "layer": layer,
                "rotation": rotation,
            },
            description=f"Place {reference} ({value}) at ({x}, {y})",
        )
        return self.backend.execute(action)

    def add_track(
        self,
        start: Tuple[float, float],
        end: Tuple[float, float],
        width_mm: float = 0.25,
        layer: str = "F.Cu",
        net: int = 0,
    ) -> ActionResult:
        action = Action(
            action_type=ActionType.ADD_TRACK,
            parameters={
                "start": start,
                "end": end,
                "width_mm": width_mm,
                "layer": layer,
                "net": net,
            },
            description=f"Route track {start} -> {end} on {layer}",
        )
        return self.backend.execute(action)

    def add_via(
        self,
        at: Tuple[float, float],
        size_mm: float = 0.8,
        drill_mm: float = 0.4,
        layers: Tuple[str, str] = ("F.Cu", "B.Cu"),
        net: int = 0,
    ) -> ActionResult:
        action = Action(
            action_type=ActionType.ADD_VIA,
            parameters={
                "at": at,
                "size_mm": size_mm,
                "drill_mm": drill_mm,
                "layers": layers,
                "net": net,
            },
            description=f"Place via at {at}",
        )
        return self.backend.execute(action)

    def add_zone(
        self,
        polygon: List[Tuple[float, float]],
        layer: str = "F.Cu",
        net: int = 0,
        net_name: str = "",
    ) -> ActionResult:
        action = Action(
            action_type=ActionType.ADD_ZONE,
            parameters={
                "polygon": polygon,
                "layer": layer,
                "net": net,
                "net_name": net_name,
            },
            description=f"Create copper zone for net '{net_name}' on {layer}",
        )
        return self.backend.execute(action)

    def get_state(self) -> ActionResult:
        action = Action(
            action_type=ActionType.GET_STATE,
            description="Query current PCB state",
        )
        return self.backend.execute(action)
