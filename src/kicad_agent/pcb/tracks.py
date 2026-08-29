"""Track and trace routing management for KiCad PCB."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, List, Optional, Tuple

if TYPE_CHECKING:
    from .board import Board


class Track:
    """Represents a routed copper track segment on the PCB."""

    def __init__(
        self,
        id: str,
        start: Tuple[float, float],
        end: Tuple[float, float],
        width_mm: float = 0.25,
        layer: str = "F.Cu",
        net: int = 0,
    ):
        self.id = id
        self.start = start
        self.end = end
        self.width_mm = width_mm
        self.layer = layer
        self.net = net

    def __repr__(self) -> str:
        return (
            f"Track(start={self.start}, end={self.end}, width={self.width_mm}mm, "
            f"layer='{self.layer}', net={self.net})"
        )


class TrackManager:
    """Manages routing of copper tracks on the PCB."""

    def __init__(self, board: Board):
        self.board = board

    def _get_pcb_path(self) -> str:
        path = self.board.filepath
        if not path or not os.path.exists(path):
            raise FileNotFoundError(f"PCB file not found: {path}")
        return os.path.abspath(path)

    def add(
        self,
        start: Tuple[float, float],
        end: Tuple[float, float],
        width_mm: float = 0.25,
        layer: str = "F.Cu",
        net: int = 0,
    ) -> Track:
        """Add a single copper track segment between two coordinates."""
        from ..backends.sexpr import add_track_to_pcb
        pcb_path = self._get_pcb_path()

        track_uuid = add_track_to_pcb(
            pcb_path=pcb_path,
            start=start,
            end=end,
            width_mm=width_mm,
            layer=layer,
            net=net,
        )

        return Track(
            id=track_uuid,
            start=start,
            end=end,
            width_mm=width_mm,
            layer=layer,
            net=net,
        )

    def route(
        self,
        points: List[Tuple[float, float]],
        width_mm: float = 0.25,
        layer: str = "F.Cu",
        net: int = 0,
    ) -> List[Track]:
        """Route a multi-segment continuous copper track through a series of points."""
        if len(points) < 2:
            raise ValueError("Routing requires at least 2 points.")

        tracks = []
        for i in range(len(points) - 1):
            t = self.add(
                start=points[i],
                end=points[i + 1],
                width_mm=width_mm,
                layer=layer,
                net=net,
            )
            tracks.append(t)
        return tracks
