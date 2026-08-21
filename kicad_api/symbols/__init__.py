"""KiCad Symbol Library Knowledge Layer.

Provides understanding of KiCad symbol definitions:
- What pins does Device:R have?
- What are the pin positions?
- What properties does a symbol expose?

This is different from placing symbols (that's kicad_api/schematic/).
"""

from .pins import PinInfo
from .symbol import SymbolInfo
from .library import SymbolLibraryParser
from .resolver import SymbolResolver

__all__ = [
    "PinInfo",
    "SymbolInfo",
    "SymbolLibraryParser",
    "SymbolResolver",
]
