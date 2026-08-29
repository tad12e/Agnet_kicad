"""Structured PCB state representation for planning and verification."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class PCBState:
    """Snapshot representation of the PCB board state.
    
    Attributes:
        board_file: Path to .kicad_pcb file.
        component_count: Total placed footprint count.
        components: List of component dictionaries (ref, value, x, y, layer, etc.).
        nets: List of net names on the board.
        unconnected_pads: Count of unrouted/unconnected pads.
        drc_errors: Count of DRC violations.
        tracks_count: Total track segments.
        vias_count: Total vias.
        zones_count: Total copper pour zones.
        metadata: Extra metadata from backend.
    """
    board_file: str = ""
    component_count: int = 0
    components: List[Dict[str, Any]] = field(default_factory=list)
    nets: List[str] = field(default_factory=list)
    unconnected_pads: int = 0
    drc_errors: int = 0
    tracks_count: int = 0
    vias_count: int = 0
    zones_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_component(self, ref: str) -> Optional[Dict[str, Any]]:
        """Look up component by reference designator."""
        for c in self.components:
            if c.get("ref") == ref or c.get("reference") == ref:
                return c
        return None
