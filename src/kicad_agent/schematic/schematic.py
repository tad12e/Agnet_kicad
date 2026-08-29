"""Schematic domain abstraction and manager coordinator."""

from __future__ import annotations

import os
from typing import Optional

from ..backends.base import KiCadBackend
from ..backends.sexpr import SexprBackend
from ..ipc.client import KiCadIPCClient
from .buses import BusManager
from .junctions import JunctionManager
from .labels import LabelManager
from .operations import ComponentManager, SchematicOperations
from .wires import WireManager


class Schematic:
    """High-level Schematic representation coordinating sub-managers."""

    def __init__(
        self,
        filepath: Optional[str] = None,
        backend: Optional[KiCadBackend] = None,
        client: Optional[KiCadIPCClient] = None,
    ):
        self.filepath = filepath or self._find_default_sch_file()
        self.client = client
        self.backend = backend or SexprBackend(sch_filepath=self.filepath)
        self.operations = SchematicOperations(self.backend)

        self.components = ComponentManager(self)
        self.wires = WireManager(self)
        self.junctions = JunctionManager(self)
        self.labels = LabelManager(self)
        self.buses = BusManager(self)

    def _find_default_sch_file(self) -> Optional[str]:
        candidates = [
            os.path.join(os.getcwd(), "first.kicad_sch"),
            os.path.join(os.getcwd(), "Agent.kicad_sch"),
        ]
        for c in candidates:
            if os.path.exists(c):
                return os.path.abspath(c)
        return None


# Backward compatibility alias
SchematicAPI = Schematic
