"""Focused tests for explicit backend selection and truthful file results."""

import os

from kicad_agent.backends.sexpr import SexprBackend
from kicad_agent.core.actions import Action, ActionType
from kicad_agent.mcp.session import MCPSession


def test_ipc_mode_does_not_silently_attach_sexpr_fallback():
    session = MCPSession(mode="ipc")
    assert session.sch_backend.fallback is None
    assert session.pcb_backend.fallback is None


def test_ipc_fallback_mode_explicitly_attaches_sexpr():
    session = MCPSession(mode="ipc-fallback")
    assert session.sch_backend.fallback is session.file_backend
    assert session.pcb_backend.fallback is session.file_backend


def test_sexpr_rejects_unsupported_operation_without_claiming_success(tmp_path):
    pcb_file = os.path.join(str(tmp_path), "board.kicad_pcb")
    with open(pcb_file, "w", encoding="utf-8") as f:
        f.write("(kicad_pcb (version 20240108) (generator pcbnew)\n)\n")

    result = SexprBackend(pcb_filepath=pcb_file).execute(
        Action(
            action_type=ActionType.MOVE_FOOTPRINT,
            parameters={"reference": "R1", "x": 10.0, "y": 10.0},
        )
    )

    assert result.success is False
    assert result.error is not None
    assert "does not support" in result.error.message
