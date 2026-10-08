"""Unit tests for IPCBackend schematic failover to a fallback backend (Part 6).

Refused/unmapped schematic actions must delegate to the fallback with honest
markers; PCB actions must never fail over; absent fallback preserves failure.
"""

import os

from kicad_agent.backends.ipc import IPCBackend
from kicad_agent.backends.sexpr import SexprBackend
from kicad_agent.core.actions import Action, ActionDomain, ActionType
from kicad_agent.ipc.exceptions import IPCRequestError
from kicad_agent.ipc.messages import ApiStatusCode

SCH_SEED = '(kicad_sch (version 20260306) (generator "eeschema")\n)\n'


class _RefusingClient:
    """Fails every send like a KiCad 10.0.4 schematic commit refusal."""

    is_connected = True

    def send(self, command, response_type):
        raise IPCRequestError(
            status_code=ApiStatusCode.AS_NOT_READY,
            error_message="KiCad is not ready to reply",
        )


def _scratch_schematic(tmp_path):
    sch_file = os.path.join(str(tmp_path), "fallback.kicad_sch")
    with open(sch_file, "w", encoding="utf-8") as f:
        f.write(SCH_SEED)
    return SexprBackend(sch_filepath=sch_file), sch_file


def _symbol_action():
    return Action(
        action_type=ActionType.ADD_SYMBOL,
        domain=ActionDomain.SCHEMATIC,
        parameters={
            "lib_id": "Device:R",
            "reference": "R99",
            "value": "10k",
            "x": 100.0,
            "y": 100.0,
        },
    )


def test_unmapped_schematic_action_fails_over_without_server_contact(tmp_path):
    fallback, sch_file = _scratch_schematic(tmp_path)
    backend = IPCBackend(client=_RefusingClient(), fallback=fallback)
    result = backend.execute(_symbol_action())
    assert result.success is True
    assert result.data["fallback_used"] is True
    assert result.data["reference"] == "R99"
    assert result.backend_used == "ipc->sexpr"
    assert "not yet mapped" in result.data["ipc_error"]
    with open(sch_file, encoding="utf-8") as f:
        assert "R99" in f.read()


def test_refused_live_action_fails_over(tmp_path):
    fallback, _ = _scratch_schematic(tmp_path)
    backend = IPCBackend(client=_RefusingClient(), fallback=fallback)
    action = Action(
        action_type=ActionType.ADD_JUNCTION,
        domain=ActionDomain.SCHEMATIC,
        parameters={"position": (10.0, 20.0)},
    )
    result = backend.execute(action)
    # sexpr has no junction support: failover engaged (marked) but the
    # fallback itself honestly rejects. No phantom success either way.
    assert result.data["fallback_used"] is True
    assert result.backend_used == "ipc->sexpr"
    assert "not ready" in result.data["ipc_error"]
    assert result.success is False
    assert result.data["fallback_success"] is False
    assert result.data["fallback_error"]["category"] == "INVALID_ACTION"


def test_fallback_failure_preserves_ipc_and_fallback_diagnostics(tmp_path):
    fallback, _ = _scratch_schematic(tmp_path)
    backend = IPCBackend(client=_RefusingClient(), fallback=fallback)
    result = backend.execute(
        Action(
            action_type=ActionType.ADD_JUNCTION,
            domain=ActionDomain.SCHEMATIC,
            parameters={"position": (10.0, 20.0)},
        )
    )
    assert result.success is False
    assert result.data["ipc_error"]
    assert result.data["fallback_success"] is False
    assert result.data["fallback_error"]["message"]


def test_pcb_actions_never_fail_over(tmp_path):
    fallback, _ = _scratch_schematic(tmp_path)
    backend = IPCBackend(client=_RefusingClient(), fallback=fallback)
    action = Action(
        action_type=ActionType.ADD_FOOTPRINT,
        domain=ActionDomain.PCB,
        parameters={"reference": "R1", "x": 1.0, "y": 1.0},
    )
    result = backend.execute(action)
    assert result.success is False
    assert result.backend_used == "ipc"
    assert "fallback_used" not in (result.data or {})


def test_absent_fallback_preserves_failure():
    backend = IPCBackend(client=_RefusingClient())
    result = backend.execute(_symbol_action())
    assert result.success is False
    assert result.backend_used == "ipc"
