"""Label and net naming management for KiCad schematics."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Optional, Tuple

if TYPE_CHECKING:
    from .schematic import Schematic


class Label:
    """Represents a net label or global label on the schematic."""

    def __init__(
        self,
        name: str,
        position_mm: Tuple[float, float],
        label_type: str = "net",
        id: Optional[str] = None,
    ):
        self.name = name
        self.position_mm = position_mm
        self.label_type = label_type
        self.id = id or str(uuid.uuid4())

    def __repr__(self) -> str:
        return f"Label(name='{self.name}', at={self.position_mm}, type='{self.label_type}')"


class LabelManager:
    """Manages schematic net and global labels."""

    def __init__(self, schematic: Schematic):
        self.schematic = schematic

    def add(self, name: str, position_mm: Tuple[float, float], label_type: str = "net") -> Label:
        return Label(name=name, position_mm=position_mm, label_type=label_type)
