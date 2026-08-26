"""Wire management for KiCad schematic."""
from __future__ import annotations

import os
import uuid
from typing import TYPE_CHECKING, Tuple, Optional

if TYPE_CHECKING:
    from .schematic import SchematicAPI


class Wire:
    """Represents a wire connection in the schematic."""

    def __init__(
        self,
        id: str,
        start: Tuple[float, float],
        end: Tuple[float, float],
    ):
        self.id = id
        self.start = start
        self.end = end

    def __repr__(self) -> str:
        return f"Wire(id='{self.id}', start={self.start}, end={self.end})"


class WireManager:
    """Manages wires in a KiCad schematic."""

    def __init__(self, schematic: SchematicAPI):
        self.schematic = schematic

    def _get_sch_path(self) -> Optional[str]:
        doc_proto = self.schematic.document_proto
        candidates = [
            getattr(self.schematic, "filepath", None),
            getattr(doc_proto, "board_filename", None),
            os.path.join(r"C:\Users\hp\ECE\test\Agent", getattr(doc_proto, "board_filename", "") or "Agent.kicad_sch"),
            os.path.join(os.getcwd(), getattr(doc_proto, "board_filename", "") or "Agent.kicad_sch"),
        ]
        for p in candidates:
            if p and os.path.exists(p):
                return os.path.abspath(p)
        return None

    def add(
        self,
        start: Tuple[float, float],
        end: Tuple[float, float],
    ) -> Wire:
        """Add a wire segment between start and end coordinates (in mm).

        Args:
            start: (x, y) start coordinate in millimeters.
            end: (x, y) end coordinate in millimeters.

        Returns:
            Created Wire object with unique ID and coordinates.
        """
        sch_path = self._get_sch_path()
        if sch_path:
            from .sexpr import add_wire_to_schematic
            wire_id = add_wire_to_schematic(sch_path, start, end)
            return Wire(id=wire_id, start=start, end=end)
        else:
            raise RuntimeError("Schematic file not found on disk to add wire.")
