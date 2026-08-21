"""Symbol metadata from KiCad symbol library definitions.

Represents a symbol definition as found in .kicad_sym library files,
NOT a placed symbol instance (that's models.Component).

The distinction:
    - SymbolInfo: Library definition — "Device:R is a resistor with 2 passive pins"
    - models.Component: Placed instance — "R1 is a 10k resistor at position (100, 100)"
"""

from __future__ import annotations

from typing import Dict, List, Optional

from .pins import PinInfo


class SymbolInfo:
    """Complete metadata for a KiCad symbol from a library file (.kicad_sym).

    Attributes:
        lib_id: Full library identifier (e.g., "Device:R").
        name: Symbol name without library prefix (e.g., "R").
        library: Library name (e.g., "Device").
        description: Human-readable description.
        keywords: Search keywords.
        pins: List of PinInfo objects describing the symbol's pins.
        properties: Dictionary of all symbol properties (Reference, Value, etc.).
        raw_sexpr: The exact S-expression string for embedding in lib_symbols.
    """

    def __init__(
        self,
        lib_id: str,
        name: str,
        library: str,
        description: str = "",
        keywords: Optional[List[str]] = None,
        pins: Optional[List[PinInfo]] = None,
        properties: Optional[Dict[str, str]] = None,
        raw_sexpr: str = "",
    ) -> None:
        self.lib_id = lib_id
        self.name = name
        self.library = library
        self.description = description
        self.keywords = keywords or []
        self.pins = pins or []
        self.properties = properties or {}
        self.raw_sexpr = raw_sexpr

    def get_pin(self, number_or_name: str) -> Optional[PinInfo]:
        """Look up a pin by number (e.g., '1') or by name (e.g., 'VCC').

        Args:
            number_or_name: Pin number or pin name to search for.

        Returns:
            Matching PinInfo, or None if not found.
        """
        query = str(number_or_name)
        for p in self.pins:
            if p.number == query or p.name == query:
                return p
        return None

    @property
    def pin_count(self) -> int:
        """Number of pins on this symbol."""
        return len(self.pins)

    def __repr__(self) -> str:
        return f"SymbolInfo(lib_id={self.lib_id!r}, pins={self.pin_count})"
