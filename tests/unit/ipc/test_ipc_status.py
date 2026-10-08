"""Focused tests for live IPC status and execution boundaries."""

from kicad_agent.backends.ipc import IPCBackend
from kicad_agent.backends.ipc_pcb import IPCPCBBackend
from kicad_agent.core.actions import Action, ActionDomain, ActionType
from kicad_agent.mcp import session as session_module
from kicad_agent.mcp.session import MCPSession


class _StatusClient:
    socket_path = "ipc://C:\\missing\\kicad\\api.sock"

    def __init__(self):
        self.is_connected = False
        self.sent = 0

    def connection_status(self):
        return {
            "connected": self.is_connected,
            "socket_path": self.socket_path,
            "socket_present": False,
            "transport_available": True,
            "timeout_ms": 100,
        }

    def send(self, command, response_type):
        self.sent += 1
        raise AssertionError("cross-domain action contacted IPC")

    def connect(self):
        self.is_connected = True

    def close(self):
        self.is_connected = False


def test_ipc_backend_reports_explicit_connection_status_without_connecting():
    client = _StatusClient()
    backend = IPCBackend(client=client)

    status = backend.connection_status()

    assert status["backend"] == "ipc"
    assert status["available"] is False
    assert status["connected"] is False
    assert status["socket_present"] is False
    assert status["fallback"] is None
    assert client.is_connected is False


def test_schematic_ipc_rejects_pcb_action_before_transport():
    client = _StatusClient()
    backend = IPCBackend(client=client)
    action = Action(action_type=ActionType.GET_STATE, domain=ActionDomain.PCB)

    result = backend.execute(action)

    assert result.success is False
    assert result.error.category.value == "INVALID_ACTION"
    assert "schematic-only" in result.error.message
    assert result.error.recoverable is False
    assert client.sent == 0


def test_pcb_ipc_rejects_schematic_action_before_transport():
    client = _StatusClient()
    backend = IPCPCBBackend(client=client)
    action = Action(action_type=ActionType.GET_STATE, domain=ActionDomain.SCHEMATIC)

    result = backend.execute(action)

    assert result.success is False
    assert result.error.category.value == "INVALID_ACTION"
    assert "PCB-only" in result.error.message
    assert result.error.recoverable is False
    assert client.sent == 0


def test_live_mcp_session_exposes_both_lane_statuses(monkeypatch):
    monkeypatch.setattr(session_module, "_ipc_socket_present", lambda _path: True)
    session = MCPSession(mode="auto", socket_path="ipc://fake")

    result = session.dispatch("session_info", {})

    assert result["status"] == "success"
    assert result["live"] is True
    assert result["ipc"]["schematic"]["backend"] == "ipc"
    assert result["ipc"]["pcb"]["backend"] == "ipc-pcb"
    assert result["ipc"]["schematic"]["connected"] is False
    assert result["ipc"]["pcb"]["connected"] is False
