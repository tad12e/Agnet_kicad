"""Footprint management for KiCad PCB."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    from .board import Board


class Footprint:
    """Represents a component footprint placed on a PCB."""

    def __init__(
        self,
        id: str,
        footprint_id: str,
        reference: str,
        value: str,
        position_mm: Tuple[float, float],
        layer: str = "F.Cu",
        rotation: float = 0,
    ):
        self.id = id
        self.footprint_id = footprint_id
        self.reference = reference
        self.value = value
        self.position_mm = position_mm
        self.layer = layer
        self.rotation = rotation

    def __repr__(self) -> str:
        return (
            f"Footprint(reference='{self.reference}', value='{self.value}', "
            f"footprint='{self.footprint_id}', at={self.position_mm}, layer='{self.layer}')"
        )


class FootprintManager:
    """Manages footprints on a PCB."""

    def __init__(self, board: Board):
        self.board = board

    def _get_pcb_path(self) -> str:
        path = self.board.filepath
        if not path or not os.path.exists(path):
            raise FileNotFoundError(f"PCB file not found: {path}")
        return os.path.abspath(path)

    def add(
        self,
        footprint_id: str,
        reference: str,
        value: str,
        position: Tuple[float, float],
        layer: str = "F.Cu",
        rotation: float = 0,
    ) -> Footprint:
        """Place a footprint on the PCB."""
        from ..backends.sexpr import add_footprint_to_pcb
        pcb_path = self._get_pcb_path()

        fp_uuid = add_footprint_to_pcb(
            pcb_path=pcb_path,
            footprint_id=footprint_id,
            reference=reference,
            value=value,
            pos_x_mm=position[0],
            pos_y_mm=position[1],
            layer=layer,
            rotation=rotation,
        )

        return Footprint(
            id=fp_uuid,
            footprint_id=footprint_id,
            reference=reference,
            value=value,
            position_mm=position,
            layer=layer,
            rotation=rotation,
        )
