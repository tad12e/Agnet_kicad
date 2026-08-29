"""KiCad Automation Backends.

Provides unified execution interfaces across:
- IPCBackend: Live socket automation (KiCad 8+)
- PcbnewBackend: Native in-process pcbnew module
- SexprBackend: Direct file S-expression parser/writer fallback
"""

from .base import KiCadBackend
from .ipc import IPCBackend
from .pcbnew import PcbnewBackend
from .sexpr import (
    KiCad10SchematicWriter,
    SexprBackend,
    add_footprint_to_pcb,
    add_symbol_to_schematic,
    add_track_to_pcb,
    add_via_to_pcb,
    add_wire_to_schematic,
    add_zone_to_pcb,
    extract_symbol_definition,
    format_sexp,
    inject_lib_symbols_into_schematic,
    parse_sexp,
)

__all__ = [
    "IPCBackend",
    "KiCad10SchematicWriter",
    "KiCadBackend",
    "PcbnewBackend",
    "SexprBackend",
    "add_footprint_to_pcb",
    "add_symbol_to_schematic",
    "add_track_to_pcb",
    "add_via_to_pcb",
    "add_wire_to_schematic",
    "add_zone_to_pcb",
    "extract_symbol_definition",
    "format_sexp",
    "inject_lib_symbols_into_schematic",
    "parse_sexp",
]
