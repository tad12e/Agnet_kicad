"""Wire management for KiCad schematic."""

from __future__ import annotations

import os
import uuid
from typing import TYPE_CHECKING, Optional, Tuple

if TYPE_CHECKING:
    from .schematic import Schematic


class Wire:
    """Represents a straight wire connection on the schematic canvas."""

    def __init__(
        self,
        id: str,
        start: Tuple[float, float],
        end: Tuple[float, float],
    ):
        self.id = id
        self.start = (float(start[0]), float(start[1]))
        self.end = (float(end[0]), float(end[1]))

    @property
    def start_mm(self) -> Tuple[float, float]:
        return self.start

    @property
    def end_mm(self) -> Tuple[float, float]:
        return self.end

    def __repr__(self) -> str:
        return f"Wire(id='{self.id}', start={self.start}, end={self.end})"


class WireManager:
    """Manages wires in a KiCad schematic."""

    def __init__(self, schematic: Schematic):
        self.schematic = schematic

    def add(
        self,
        start: Tuple[float, float],
        end: Tuple[float, float],
    ) -> Wire:
        """Add a wire segment connecting start and end coordinates in mm."""
        from ..backends.sexpr import add_wire_to_schematic
        sch_path = self.schematic.filepath
        if sch_path and os.path.exists(sch_path):
            wire_id = add_wire_to_schematic(sch_path, start, end)
            return Wire(id=wire_id, start=start, end=end)
        else:
            wire_id = str(uuid.uuid4())
            return Wire(id=wire_id, start=start, end=end)
