"""Zone and copper pour management for KiCad PCB."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, List, Tuple

if TYPE_CHECKING:
    from .board import Board


class Zone:
    """Represents a copper pour zone on the PCB."""

    def __init__(
        self,
        id: str,
        polygon: List[Tuple[float, float]],
        layer: str = "F.Cu",
        net: int = 0,
        net_name: str = "",
    ):
        self.id = id
        self.polygon = polygon
        self.layer = layer
        self.net = net
        self.net_name = net_name

    def __repr__(self) -> str:
        return f"Zone(net='{self.net_name}', layer='{self.layer}', vertices={len(self.polygon)})"


class ZoneManager:
    """Manages copper pour zones on the PCB."""

    def __init__(self, board: Board):
        self.board = board

    def _get_pcb_path(self) -> str:
        path = self.board.filepath
        if not path or not os.path.exists(path):
            raise FileNotFoundError(f"PCB file not found: {path}")
        return os.path.abspath(path)

    def add(
        self,
        polygon: List[Tuple[float, float]],
        layer: str = "F.Cu",
        net: int = 0,
        net_name: str = "",
    ) -> Zone:
        """Add a polygon copper zone / pour to the PCB."""
        if len(polygon) < 3:
            raise ValueError("A zone polygon must have at least 3 vertices.")

        from ..backends.sexpr import add_zone_to_pcb
        pcb_path = self._get_pcb_path()

        zone_uuid = add_zone_to_pcb(
            pcb_path=pcb_path,
            polygon=polygon,
            layer=layer,
            net=net,
            net_name=net_name,
        )

        return Zone(
            id=zone_uuid,
            polygon=polygon,
            layer=layer,
            net=net,
            net_name=net_name,
        )
