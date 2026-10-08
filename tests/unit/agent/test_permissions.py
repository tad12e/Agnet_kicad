from kicad_agent.agent.tools import ToolRegistry
from kicad_agent.core.contracts import PermissionDecision
from kicad_agent.core.permissions import PermissionPolicy


class FakeBackend:
    def __init__(self):
        self.executed = []

    def get_state(self, domain):
        return {"components": [{"ref": "U1"}]}

    def execute(self, action):
        self.executed.append(action)
        class Result:
            success = True
            data = {"ok": True}
            error = None
        return Result()


def test_registry_returns_approval_request_before_delete():
    backend = FakeBackend()
    registry = ToolRegistry(backend)

    result = registry.execute_tool(
        "delete_symbol", {"reference": "U1"}, domain="schematic"
    )

    assert result["status"] == "approval_required"
    assert result["code"] == "APPROVAL_REQUIRED"
    assert result["approval_request"]["action"]["action_type"] == "delete_symbol"
    assert backend.executed == []


def test_registry_executes_only_after_explicit_approval():
    backend = FakeBackend()
    registry = ToolRegistry(backend)
    action = registry.execute_tool(
        "delete_symbol",
        {"reference": "U1"},
        domain="schematic",
        approval=PermissionDecision.ALLOW,
    )

    assert action["status"] == "success"
    assert len(backend.executed) == 1
