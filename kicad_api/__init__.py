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

import os
import sys

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_LOCAL_SITE = os.path.join(_ROOT, ".site-packages")
if os.path.exists(_LOCAL_SITE) and _LOCAL_SITE not in sys.path:
    sys.path.insert(0, _LOCAL_SITE)

from .ipc.client import KiCadIPCClient
from .schematic.schematic import SchematicAPI

__all__ = ["KiCadIPCClient", "SchematicAPI"]
