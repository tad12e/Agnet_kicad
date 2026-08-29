"""Junction dot management for KiCad schematics."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Optional, Tuple

if TYPE_CHECKING:
    from .schematic import Schematic


class Junction:
    """Represents an electrical junction dot on the schematic."""

    def __init__(
        self,
        position_mm: Tuple[float, float],
        id: Optional[str] = None,
    ):
        self.position_mm = (float(position_mm[0]), float(position_mm[1]))
        self.id = id or str(uuid.uuid4())

    def __repr__(self) -> str:
        return f"Junction(at={self.position_mm}, id={self.id})"


class JunctionManager:
    """Manages junction dots on the schematic."""

    def __init__(self, schematic: Schematic):
        self.schematic = schematic

    def add(self, position_mm: Tuple[float, float]) -> Junction:
        """Place a junction dot at the given coordinates."""
        return Junction(position_mm=position_mm)
