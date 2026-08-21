"""Client-side representation of a placed schematic component/symbol.

This is an ADAPTER model — it represents what KiCad returns when you
place a symbol, NOT a replacement for KiCad's C++ SCH_SYMBOL.

C++ context:
    In KiCad, SCH_SYMBOL (defined in eeschema/sch_symbol.h) is the actual
    schematic symbol object. It inherits from SCH_ITEM and holds:
    - LIB_ID m_lib_id          (library identifier, e.g., "Device:R")
    - SCH_FIELD m_fields[]     (reference, value, footprint, datasheet, ...)
    - VECTOR2I m_pos           (position in internal units)
    - int m_unit               (symbol unit for multi-unit parts)
    - TRANSFORM m_transform    (rotation/mirror matrix)

    Our Python Component is a lightweight snapshot of the data KiCad
    sends back over IPC. KiCad remains the source of truth.
"""

from __future__ import annotations

from typing import Optional, Tuple


class Component:
    """Represents a placed schematic symbol (e.g., Resistor R1, Capacitor C1).

    Attributes:
        id: KiCad-assigned UUID (KIID) for this symbol instance.
        lib_id: Library identifier, e.g., "Device:R" or "Timer:NE555".
        reference: Reference designator, e.g., "R1", "C1", "U1".
        value: Component value string, e.g., "10k", "100nF".
        position_mm: (X, Y) position in millimeters.
        unit: Symbol unit number (for multi-unit symbols like op-amps).
        raw_proto: Optional reference to the original protobuf message.
    """

    def __init__(
        self,
        id: str,
        lib_id: str,
        reference: str,
        value: str,
        position_mm: Tuple[float, float],
        unit: int = 1,
        raw_proto: Optional[object] = None,
    ):
        self.id = id
        self.lib_id = lib_id
        self.reference = reference
        self.value = value
        self.position_mm = position_mm
        self.unit = unit
        self._raw_proto = raw_proto

    def __repr__(self) -> str:
        return (
            f"Component(ref={self.reference!r}, val={self.value!r}, "
            f"lib={self.lib_id!r}, pos={self.position_mm}, id={self.id!r})"
        )
