"""Client-side representation of a schematic wire segment.

This is an ADAPTER model — it represents wire data from KiCad,
NOT a replacement for KiCad's C++ SCH_LINE.

C++ context:
    In KiCad, SCH_LINE (defined in eeschema/sch_line.h) represents a
    single straight-line segment on the schematic. It inherits from SCH_ITEM
    and holds:
    - VECTOR2I m_start    (start point)
    - VECTOR2I m_end      (end point)
    - LINE_TYPE m_layer   (SLT_WIRE for electrical wires, SLT_BUS for buses)

    SCH_LINE with layer SLT_WIRE is what creates electrical connections
    between component pins. The connectivity engine (CONNECTION_GRAPH)
    traces these wires to build nets.
"""

from __future__ import annotations

import uuid as _uuid
from typing import Optional, Tuple


class Wire:
    """Represents a straight schematic wire between two points.

    Attributes:
        start_mm: (X, Y) start position in millimeters.
        end_mm: (X, Y) end position in millimeters.
        id: UUID for this wire segment.
    """

    def __init__(
        self,
        start_mm: Tuple[float, float],
        end_mm: Tuple[float, float],
        id: Optional[str] = None,
    ):
        self.start_mm = (float(start_mm[0]), float(start_mm[1]))
        self.end_mm = (float(end_mm[0]), float(end_mm[1]))
        self.id = id or str(_uuid.uuid4())

    def __repr__(self) -> str:
        return f"Wire({self.start_mm} -> {self.end_mm})"
