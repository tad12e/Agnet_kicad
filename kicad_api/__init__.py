"""KiCad IPC Python API Adapter.

Official IPC API adapter for KiCad 8/9/10/11+.
Provides a clean Python interface over KiCad's protobuf-based IPC API.

Architecture:
    kicad_api/
    ├── ipc/         → Transport layer (NNG socket, protobuf envelopes)
    ├── schematic/   → High-level schematic API (components, wires, etc.)
    ├── models/      → Client-side data representations
    ├── symbols/     → Symbol library knowledge (parsing, lookup)
    └── geometry/    → Coordinate conversion utilities
"""

from .ipc.client import KiCadIPCClient
from .schematic.schematic import SchematicAPI

__all__ = ["KiCadIPCClient", "SchematicAPI"]
