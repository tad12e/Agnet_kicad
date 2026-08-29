"""KiCad PCB Domain Package.

Pure PCB domain concepts, geometric transformations, and component managers.
"""

from .board import Board
from .footprints import Footprint, FootprintManager
from .geometry import BoundingBox, Point, mm_pair_to_nm, mm_to_nm, nm_pair_to_mm, nm_to_mm
from .nets import PcbNet, PcbNetManager
from .operations import PCBOperations
from .pads import Pad
from .state import PCBState
from .tracks import Track, TrackManager
from .vias import Via, ViaManager
from .zones import Zone, ZoneManager

# Legacy alias for backward compatibility
PcbAPI = Board

__all__ = [
    "Board",
    "BoundingBox",
    "Footprint",
    "FootprintManager",
    "PCBOperations",
    "PCBState",
    "Pad",
    "PcbAPI",
    "PcbNet",
    "PcbNetManager",
    "Point",
    "Track",
    "TrackManager",
    "Via",
    "ViaManager",
    "Zone",
    "ZoneManager",
    "mm_pair_to_nm",
    "mm_to_nm",
    "nm_pair_to_mm",
    "nm_to_mm",
]
