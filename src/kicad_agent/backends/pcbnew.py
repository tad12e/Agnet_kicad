"""Pcbnew Python API Backend.

Communicates in-process with KiCad's native pcbnew module for direct board
manipulation and DRC checks.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List, Optional, Tuple

from ..core.actions import Action, ActionType
from ..core.errors import AgentError, ErrorCategory
from ..core.results import ActionResult
from ..utils.paths import get_kicad_footprints_dir
from .base import KiCadBackend


def mm_to_pcbnew(val: float) -> int:
    """Convert mm to pcbnew internal units (nanometers)."""
    return int(val * 1e6)


def pcbnew_to_mm(val: int) -> float:
    """Convert pcbnew internal units (nanometers) to mm."""
    return round(val / 1e6, 4)


FOOTPRINT_MAP = {
    "resistor": ("Resistor_SMD.pretty", "R_0402_1005Metric"),
    "capacitor": ("Capacitor_SMD.pretty", "C_0402_1005Metric"),
    "led": ("LED_SMD.pretty", "LED_0402_1005Metric"),
    "inductor": ("Inductor_SMD.pretty", "L_0402_1005Metric"),
}


def resolve_footprint_name(lib_path: str, name: str) -> str:
    """Find exact .kicad_mod file within a .pretty library folder."""
    exact_file = os.path.join(lib_path, f"{name}.kicad_mod")
    if os.path.exists(exact_file):
        return name
    if os.path.exists(lib_path):
        try:
            for fname in os.listdir(lib_path):
                if fname.startswith(name) and fname.endswith(".kicad_mod"):
                    return fname[:-10]
        except Exception:
            pass
    return name


class PcbnewBackend(KiCadBackend):
    """In-process native pcbnew Python module backend."""

    def __init__(self):
        self._pcbnew = None
        self._board = None

    @property
    def name(self) -> str:
        return "pcbnew"

    def is_available(self) -> bool:
        try:
            import pcbnew  # type: ignore[import]
            return True
        except ImportError:
            return False

    def connect(self) -> None:
        if self._pcbnew is not None:
            return
        try:
            import pcbnew  # type: ignore[import]
            self._pcbnew = pcbnew
        except ImportError as e:
            raise AgentError(
                category=ErrorCategory.API_ERROR,
                message="pcbnew Python module is not available in this environment",
            ) from e

    def disconnect(self) -> None:
        self._pcbnew = None
        self._board = None

    def _get_board(self):
        if self._pcbnew is None:
            self.connect()
        board = self._pcbnew.GetBoard()
        if board is None:
            if self._board is not None:
                return self._board
            if hasattr(self._pcbnew, "BOARD"):
                self._board = self._pcbnew.BOARD()
                return self._board
        return board

    def load_board(self, filepath: str) -> Dict[str, Any]:
        if self._pcbnew is None:
            self.connect()
        if hasattr(self._pcbnew, "LoadBoard"):
            self._board = self._pcbnew.LoadBoard(filepath)
        return self.get_state("pcb")

    def save_board(self, filepath: Optional[str] = None) -> bool:
        board = self._get_board()
        path = filepath or (board.GetFileName() if hasattr(board, "GetFileName") else "")
        if not path:
            raise AgentError(category=ErrorCategory.FILE_ERROR, message="No filepath provided to save board")
        if hasattr(board, "Save"):
            board.Save(path)
        return True

    def load_schematic(self, filepath: str) -> Dict[str, Any]:
        raise NotImplementedError("pcbnew backend does not manage schematics")

    def save_schematic(self, filepath: Optional[str] = None) -> bool:
        raise NotImplementedError("pcbnew backend does not manage schematics")

    def get_state(self, domain: str = "pcb") -> Dict[str, Any]:
        board = self._get_board()
        components = []
        if hasattr(board, "GetFootprints"):
            for fp in board.GetFootprints():
                components.append({
                    "ref": fp.GetReference(),
                    "value": fp.GetValue(),
                    "x": pcbnew_to_mm(fp.GetX()),
                    "y": pcbnew_to_mm(fp.GetY()),
                    "layer": fp.GetLayerName(),
                })

        nets = []
        if hasattr(board, "GetNetInfo"):
            for net in board.GetNetInfo().NetsByName().values():
                name = net.GetNetname()
                if name:
                    nets.append(name)

        unconnected = 0
        if hasattr(board, "GetConnectivity"):
            connectivity = board.GetConnectivity()
            if hasattr(connectivity, "RecalculateRatsnest"):
                connectivity.RecalculateRatsnest()
            if hasattr(connectivity, "GetUnconnectedCount"):
                unconnected = connectivity.GetUnconnectedCount(False)

        return {
            "component_count": len(components),
            "components": components,
            "nets": nets,
            "unconnected_pads": unconnected,
            "board_file": board.GetFileName() if hasattr(board, "GetFileName") else "",
        }

    def run_drc(self) -> Dict[str, Any]:
        board = self._get_board()
        unconnected = 0
        if hasattr(board, "GetConnectivity"):
            connectivity = board.GetConnectivity()
            if hasattr(connectivity, "RecalculateRatsnest"):
                connectivity.RecalculateRatsnest()
            if hasattr(connectivity, "GetUnconnectedCount"):
                unconnected = connectivity.GetUnconnectedCount(False)
        return {
            "status": "clean" if unconnected == 0 else "has errors",
            "unconnected_count": unconnected,
        }

    def execute(self, action: Action) -> ActionResult:
        t0 = time.time()
        p = action.parameters

        try:
            board = self._get_board()

            if action.action_type == ActionType.GET_STATE:
                state = self.get_state("pcb")
                return ActionResult(
                    action_id=action.action_id,
                    success=True,
                    data=state,
                    execution_time_ms=(time.time() - t0) * 1000,
                    backend_used=self.name,
                )

            elif action.action_type == ActionType.ADD_FOOTPRINT:
                ref = p["reference"]
                val = p.get("value", "")
                x = p["x"]
                y = p["y"]
                comp_type = p.get("component_type", "resistor")
                footprint_lib = p.get("footprint_lib")
                footprint_name = p.get("footprint_name")

                existing = [fp.GetReference() for fp in board.GetFootprints()] if hasattr(board, "GetFootprints") else []
                if ref in existing:
                    raise AgentError(
                        category=ErrorCategory.PLACEMENT_ERROR,
                        message=f"{ref} already exists on the board",
                        target_object=ref,
                    )

                if not footprint_lib or not footprint_name:
                    if comp_type in FOOTPRINT_MAP:
                        footprint_lib, footprint_name = FOOTPRINT_MAP[comp_type]
                    else:
                        footprint_lib, footprint_name = "Resistor_SMD.pretty", "R_0402"

                footprint_base = get_kicad_footprints_dir()
                lib_path = os.path.join(footprint_base, footprint_lib)
                actual_name = resolve_footprint_name(lib_path, footprint_name)
                
                fp = None
                if hasattr(self._pcbnew, "FootprintLoad"):
                    fp = self._pcbnew.FootprintLoad(lib_path, actual_name)

                if fp is None:
                    raise AgentError(
                        category=ErrorCategory.PLACEMENT_ERROR,
                        message=f"Could not load footprint '{actual_name}' from '{lib_path}'",
                        target_object=ref,
                    )

                if hasattr(fp, "SetReference"):
                    fp.SetReference(ref)
                if hasattr(fp, "SetValue"):
                    fp.SetValue(val)
                if hasattr(fp, "SetPosition"):
                    if hasattr(self._pcbnew, "VECTOR2I"):
                        fp.SetPosition(self._pcbnew.VECTOR2I(mm_to_pcbnew(x), mm_to_pcbnew(y)))
                if hasattr(board, "Add"):
                    board.Add(fp)

                return ActionResult(
                    action_id=action.action_id,
                    success=True,
                    data={"reference": ref, "value": val, "x": x, "y": y},
                    execution_time_ms=(time.time() - t0) * 1000,
                    backend_used=self.name,
                )

            elif action.action_type == ActionType.ADD_TRACK:
                x1, y1 = p.get("start", (p.get("x1", 0), p.get("y1", 0)))
                x2, y2 = p.get("end", (p.get("x2", 0), p.get("y2", 0)))
                width_mm = p.get("width_mm", 0.25)

                if hasattr(self._pcbnew, "PCB_TRACK"):
                    track = self._pcbnew.PCB_TRACK(board)
                    track.SetStart(self._pcbnew.VECTOR2I(mm_to_pcbnew(x1), mm_to_pcbnew(y1)))
                    track.SetEnd(self._pcbnew.VECTOR2I(mm_to_pcbnew(x2), mm_to_pcbnew(y2)))
                    track.SetWidth(mm_to_pcbnew(width_mm))
                    track.SetLayer(getattr(self._pcbnew, "F_Cu", 0))
                    if hasattr(board, "Add"):
                        board.Add(track)

                return ActionResult(
                    action_id=action.action_id,
                    success=True,
                    data={"start": (x1, y1), "end": (x2, y2), "width_mm": width_mm},
                    execution_time_ms=(time.time() - t0) * 1000,
                    backend_used=self.name,
                )

            elif action.action_type == ActionType.RUN_DRC:
                drc_result = self.run_drc()
                return ActionResult(
                    action_id=action.action_id,
                    success=True,
                    data=drc_result,
                    execution_time_ms=(time.time() - t0) * 1000,
                    backend_used=self.name,
                )

            elif action.action_type == ActionType.SAVE_DOCUMENT:
                self.save_board()
                return ActionResult(
                    action_id=action.action_id,
                    success=True,
                    data={"saved": True},
                    execution_time_ms=(time.time() - t0) * 1000,
                    backend_used=self.name,
                )

            else:
                raise AgentError(
                    category=ErrorCategory.INVALID_ACTION,
                    message=f"PcbnewBackend does not support action {action.action_type}",
                )

        except Exception as e:
            err = e if isinstance(e, AgentError) else AgentError(
                category=ErrorCategory.API_ERROR,
                message=str(e),
                operation=action.action_type.value,
            )
            return ActionResult(
                action_id=action.action_id,
                success=False,
                error=err,
                execution_time_ms=(time.time() - t0) * 1000,
                backend_used=self.name,
            )
