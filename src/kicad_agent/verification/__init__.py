"""KiCad Verification Architecture.

Independent verification layer for placement, connectivity, geometry, DRC, and intent.
"""

from .base import BaseVerifier
from .connectivity import ConnectivityVerifier
from .drc import DRCVerifier
from .geometry import GeometryVerifier
from .intent import IntentVerifier
from .placement import PlacementVerifier
from .routing import RoutingVerifier
from .simulation import run_ngspice_simulation
from .structural import StructuralVerifier

__all__ = [
    "BaseVerifier",
    "ConnectivityVerifier",
    "DRCVerifier",
    "GeometryVerifier",
    "IntentVerifier",
    "PlacementVerifier",
    "RoutingVerifier",
    "StructuralVerifier",
    "run_ngspice_simulation",
]
