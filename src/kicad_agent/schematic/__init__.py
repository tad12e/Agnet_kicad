"""KiCad Schematic Domain Package.

Pure Schematic domain concepts, symbol parsers, resolver, wiring, and state models.
"""

from .buses import Bus, BusManager
from .junctions import Junction, JunctionManager
from .labels import Label, LabelManager
from .operations import ComponentManager, SchematicOperations
from .schematic import Schematic, SchematicAPI
from .state import SchematicState
from .symbols import (
    Component,
    Pin,
    PinInfo,
    SymbolInfo,
    SymbolLibraryParser,
    SymbolResolver,
)
from .wires import Wire, WireManager

__all__ = [
    "Bus",
    "BusManager",
    "Component",
    "ComponentManager",
    "Junction",
    "JunctionManager",
    "Label",
    "LabelManager",
    "Pin",
    "PinInfo",
    "Schematic",
    "SchematicAPI",
    "SchematicOperations",
    "SchematicState",
    "SymbolInfo",
    "SymbolLibraryParser",
    "SymbolResolver",
    "Wire",
    "WireManager",
]
