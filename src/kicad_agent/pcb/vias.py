"""Via management for KiCad PCB."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Tuple

if TYPE_CHECKING:
    from .board import Board


class Via:
    """Represents a via connecting copper layers on the PCB."""

    def __init__(
        self,
        id: str,
        at: Tuple[float, float],
        size_mm: float = 0.8,
        drill_mm: float = 0.4,
        layers: Tuple[str, str] = ("F.Cu", "B.Cu"),
        net: int = 0,
    ):
        self.id = id
        self.at = at
        self.size_mm = size_mm
        self.drill_mm = drill_mm
        self.layers = layers
        self.net = net

    def __repr__(self) -> str:
        return (
            f"Via(at={self.at}, size={self.size_mm}mm, drill={self.drill_mm}mm, "
            f"layers={self.layers}, net={self.net})"
        )


class ViaManager:
    """Manages vias on the PCB."""

    def __init__(self, board: Board):
        self.board = board

    def _get_pcb_path(self) -> str:
        path = self.board.filepath
        if not path or not os.path.exists(path):
            raise FileNotFoundError(f"PCB file not found: {path}")
        return os.path.abspath(path)

    def add(
        self,
        at: Tuple[float, float],
        size_mm: float = 0.8,
        drill_mm: float = 0.4,
        layers: Tuple[str, str] = ("F.Cu", "B.Cu"),
        net: int = 0,
    ) -> Via:
        """Place a via on the PCB."""
        from ..backends.sexpr import add_via_to_pcb
        pcb_path = self._get_pcb_path()

        via_uuid = add_via_to_pcb(
            pcb_path=pcb_path,
            at=at,
            size_mm=size_mm,
            drill_mm=drill_mm,
            layers=layers,
            net=net,
        )

        return Via(
            id=via_uuid,
            at=at,
            size_mm=size_mm,
            drill_mm=drill_mm,
            layers=layers,
            net=net,
        )
