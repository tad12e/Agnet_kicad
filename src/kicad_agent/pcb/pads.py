"""Pad entity representation on a PCB footprint."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass
class Pad:
    """Represents a physical pad on a footprint.
    
    Attributes:
        number: Pad number/name (e.g. '1', '2', 'GND').
        position_mm: World coordinate in mm.
        net_name: Associated net name.
        net_code: Net ID integer code.
        layer: Copper layer (e.g. 'F.Cu', '*.Cu').
        size_mm: (width, height) of pad in mm.
        drill_mm: Hole drill diameter in mm for THT pads.
    """
    number: str
    position_mm: Tuple[float, float]
    net_name: str = ""
    net_code: int = 0
    layer: str = "F.Cu"
    size_mm: Tuple[float, float] = (1.0, 1.0)
    drill_mm: float = 0.0
