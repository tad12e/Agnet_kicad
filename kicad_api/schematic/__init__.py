"""KiCad Schematic API Module.

High-level interface for schematic operations via KiCad IPC.
"""

from .schematic import SchematicAPI
from .components import ComponentManager

__all__ = ["SchematicAPI", "ComponentManager"]
