"""Pin metadata from KiCad symbol library definitions.

This represents a pin as defined in a .kicad_sym library file,
NOT a pin on a placed component instance (that's models.Pin).

The distinction:
    - PinInfo: Library definition — "Device:R has pin 1 at local offset (0, 3.81)"
    - models.Pin: Placed instance — "R1's pin 1 is at world position (100, 96.19)"
"""

from __future__ import annotations


class PinInfo:
    """Metadata for a single pin on a KiCad symbol definition.

    Extracted from .kicad_sym library files. The coordinates (at_x, at_y)
    are LOCAL to the symbol — they need to be transformed by the symbol's
    position and rotation to get world coordinates.

    Attributes:
        number: Pin number string (e.g., "1", "2", "A1").
        name: Pin display name (e.g., "VCC", "" for hidden).
        pin_type: Electrical type (e.g., "passive", "input", "output", "power_in").
        at_x: Local X offset from symbol origin (in mm, KiCad library units).
        at_y: Local Y offset from symbol origin.
        orientation: Pin angle in degrees (0=right, 90=up, 180=left, 270=down).
    """

    def __init__(
        self,
        number: str,
        name: str,
        pin_type: str = "passive",
        at_x: float = 0.0,
        at_y: float = 0.0,
        orientation: int = 0,
    ) -> None:
        self.number = str(number)
        self.name = str(name)
        self.pin_type = str(pin_type)
        self.at_x = float(at_x)
        self.at_y = float(at_y)
        self.orientation = int(orientation)

    def __repr__(self) -> str:
        return f"PinInfo(num={self.number!r}, name={self.name!r}, type={self.pin_type!r})"
