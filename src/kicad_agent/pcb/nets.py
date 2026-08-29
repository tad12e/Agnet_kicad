"""Netlist and connectivity management for KiCad PCB."""

from __future__ import annotations

import os
import re
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from .board import Board


class PcbNet:
    """Represents an electrical net on the PCB."""

    def __init__(self, code: int, name: str):
        self.code = code
        self.name = name

    def __repr__(self) -> str:
        return f"PcbNet(code={self.code}, name='{self.name}')"


class PcbNetManager:
    """Manages PCB nets and connectivity."""

    def __init__(self, board: Board):
        self.board = board

    def _get_pcb_path(self) -> str:
        path = self.board.filepath
        if not path or not os.path.exists(path):
            raise FileNotFoundError(f"PCB file not found: {path}")
        return os.path.abspath(path)

    def list(self) -> List[PcbNet]:
        """List all nets declared in the PCB file."""
        pcb_path = self._get_pcb_path()
        with open(pcb_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        nets = []
        for m in re.finditer(r'\(net\s+(\d+)\s+"([^"]*)"\)', content):
            nets.append(PcbNet(code=int(m.group(1)), name=m.group(2)))
        return nets

    def get(self, name: str) -> Optional[PcbNet]:
        """Get a PCB net by name."""
        for net in self.list():
            if net.name == name:
                return net
        return None
