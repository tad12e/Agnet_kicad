"""Label and net naming management for KiCad schematics."""

from __future__ import annotations

import os
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

    def add(
        self,
        name: str,
        position_mm: Tuple[float, float],
        label_type: str = "net",
        rotation: float = 0,
    ) -> Label:
        from ..backends.sexpr import add_label_to_schematic
        sch_path = self.schematic.filepath
        kind = "local" if label_type == "net" else label_type
        if sch_path and os.path.exists(sch_path):
            label_id = add_label_to_schematic(
                sch_path, name, position_mm[0], position_mm[1], kind, rotation
            )
            return Label(name=name, position_mm=position_mm, label_type=label_type, id=label_id)
        else:
            return Label(name=name, position_mm=position_mm, label_type=label_type)
