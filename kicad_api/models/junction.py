"""Client-side representation of a schematic junction.

This is an ADAPTER model — it represents junction data from KiCad,
NOT a replacement for KiCad's C++ SCH_JUNCTION.

C++ context:
    In KiCad, SCH_JUNCTION (defined in eeschema/sch_junction.h) represents
    the round dot placed at wire intersections to indicate an electrical
    connection. Without a junction, two crossing wires are NOT connected.

    SCH_JUNCTION inherits from SCH_ITEM and holds:
    - VECTOR2I m_pos    (position)
    - int m_diameter    (dot diameter, 0 = default)
    - COLOR4D m_color   (dot color, default = scheme color)
"""

from __future__ import annotations

import uuid as _uuid
from typing import Optional, Tuple


class Junction:
    """Represents an electrical junction dot on the schematic.

    Attributes:
        position_mm: (X, Y) position in millimeters.
        id: UUID for this junction.
    """

    def __init__(
        self,
        position_mm: Tuple[float, float],
        id: Optional[str] = None,
    ):
        self.position_mm = (float(position_mm[0]), float(position_mm[1]))
        self.id = id or str(_uuid.uuid4())

    def __repr__(self) -> str:
        return f"Junction(at={self.position_mm})"
