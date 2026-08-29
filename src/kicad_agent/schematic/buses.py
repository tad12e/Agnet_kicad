"""Bus wiring management for KiCad schematics."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, List, Tuple

if TYPE_CHECKING:
    from .schematic import Schematic


class Bus:
    """Represents a bus line aggregating multiple net signals."""

    def __init__(
        self,
        name: str,
        start_mm: Tuple[float, float],
        end_mm: Tuple[float, float],
        id: str = "",
    ):
        self.name = name
        self.start_mm = start_mm
        self.end_mm = end_mm
        self.id = id or str(uuid.uuid4())

    def __repr__(self) -> str:
        return f"Bus(name='{self.name}', {self.start_mm} -> {self.end_mm})"


class BusManager:
    """Manages bus lines in a schematic."""

    def __init__(self, schematic: Schematic):
        self.schematic = schematic

    def add(self, name: str, start_mm: Tuple[float, float], end_mm: Tuple[float, float]) -> Bus:
        return Bus(name=name, start_mm=start_mm, end_mm=end_mm)
