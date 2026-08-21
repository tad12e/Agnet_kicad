"""Client-side representation of a pin on a placed component.

C++ context:
    In KiCad, SCH_PIN (defined in eeschema/sch_pin.h) represents a pin
    on a placed symbol instance. It references the underlying LIB_PIN
    definition from the symbol library and adds instance-specific data
    like world position (after applying the symbol's transform).

    SCH_PIN holds:
    - const LIB_PIN* m_libPin   (pointer to library pin definition)
    - VECTOR2I m_position       (world position on schematic)
    - SCH_SYMBOL* m_parent      (the symbol this pin belongs to)

    The connectivity engine uses SCH_PIN positions to determine which
    wires connect to which pins.
"""

from __future__ import annotations

from typing import Optional, Tuple


class Pin:
    """Represents a pin on a placed schematic component.

    Attributes:
        number: Pin number string (e.g., "1", "2", "A1").
        name: Pin name (e.g., "VCC", "GND", "" for unnamed).
        position_mm: World (X, Y) position after component transform.
        pin_type: Electrical type (e.g., "passive", "input", "output", "power_in").
        parent_ref: Reference designator of the parent component.
    """

    def __init__(
        self,
        number: str,
        name: str = "",
        position_mm: Optional[Tuple[float, float]] = None,
        pin_type: str = "passive",
        parent_ref: str = "",
    ):
        self.number = str(number)
        self.name = str(name)
        self.position_mm = position_mm
        self.pin_type = str(pin_type)
        self.parent_ref = parent_ref

    def __repr__(self) -> str:
        return (
            f"Pin(num={self.number!r}, name={self.name!r}, "
            f"type={self.pin_type!r}, parent={self.parent_ref!r})"
        )
