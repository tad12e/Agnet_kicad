"""PCB Board abstraction and manager coordinator."""

from __future__ import annotations

import os
from typing import Optional

from ..backends.base import KiCadBackend
from ..backends.sexpr import SexprBackend
from .footprints import FootprintManager
from .nets import PcbNetManager
from .tracks import TrackManager
from .vias import ViaManager
from .zones import ZoneManager


class Board:
    """High-level PCB Board representation coordinating sub-managers."""

    def __init__(
        self,
        filepath: Optional[str] = None,
        backend: Optional[KiCadBackend] = None,
    ):
        self.filepath = filepath or self._find_default_pcb_file()
        self.backend = backend or SexprBackend(pcb_filepath=self.filepath)

        self.footprints = FootprintManager(self)
        self.tracks = TrackManager(self)
        self.vias = ViaManager(self)
        self.zones = ZoneManager(self)
        self.nets = PcbNetManager(self)

    def _find_default_pcb_file(self) -> Optional[str]:
        candidates = [
            os.path.join(os.getcwd(), "test_board.kicad_pcb"),
            os.path.join(os.getcwd(), "Agent.kicad_pcb"),
        ]
        for c in candidates:
            if os.path.exists(c):
                return os.path.abspath(c)
        return None
