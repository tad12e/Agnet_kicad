"""Structured Schematic state representation for planning and verification."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class SchematicState:
    """Snapshot representation of the schematic canvas state.
    
    Attributes:
        schematic_file: Path to .kicad_sch file.
        symbols_count: Total placed symbol count.
        symbols: List of placed symbol dicts (ref, value, lib_id, pos, pins).
        wires: List of wire segments.
        junctions: List of junction coordinates.
        nets: List of schematic nets.
        errors: Unconnected pins or verification errors.
    """
    schematic_file: str = ""
    symbols_count: int = 0
    symbols: List[Dict[str, Any]] = field(default_factory=list)
    wires: List[Dict[str, Any]] = field(default_factory=list)
    junctions: List[Dict[str, Any]] = field(default_factory=list)
    nets: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def get_symbol(self, ref: str) -> Optional[Dict[str, Any]]:
        """Look up symbol by reference designator."""
        for s in self.symbols:
            if s.get("reference") == ref or s.get("ref") == ref:
                return s
        return None
