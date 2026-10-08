from kicad_agent.agent.loop import AgentLoop
from kicad_agent.core.session import AgentSession, MessageType
from kicad_agent.providers.llm import LLMProvider
from kicad_agent.agent.observability import AgentTrace


class ScriptedProvider(LLMProvider):
    def __init__(self):
        self.calls = []
        self.responses = [
            {
                "content": "I will inspect the board.",
                "tool_calls": [{
                    "id": "call-1",
                    "function": {
                        "name": "get_board_info",
                        "arguments": {},
                    },
                }],
            },
            {"content": "The board inspection is complete.", "tool_calls": []},
        ]

    def generate_response(self, messages, tools=None, system_prompt="", model=None):
        self.calls.append((messages, tools, system_prompt))
        return self.responses.pop(0)


def test_agent_loop_persists_tool_turn_and_continues_with_result():
    provider = ScriptedProvider()
    executed = []

    def execute(name, arguments):
        executed.append((name, arguments))
        return {"status": "success", "board": {"components": []}}

    result = AgentLoop(
        provider=provider,
        tool_executor=execute,
        tool_schemas=[{"name": "get_board_info"}],
    ).run("Inspect the board")

    assert result["status"] == "completed"
    assert result["steps"] == 2
    assert executed == [("get_board_info", {})]
    session = AgentSession.from_dict(result["session"])
    assert [message.message_type for message in session.messages] == [
        MessageType.USER,
        MessageType.TOOL_CALL,
        MessageType.TOOL_RESULT,
        MessageType.ASSISTANT,
    ]
    assert len(provider.calls) == 2
    assert provider.calls[1][0][-1]["role"] == "user"


def test_agent_loop_returns_structured_tool_errors_and_stops_at_limit():
    class EndlessProvider(LLMProvider):
        def generate_response(self, messages, tools=None, system_prompt="", model=None):
            return {
                "tool_calls": [{
                    "name": "unknown_tool",
                    "arguments": {},
                    "id": "call-endless",
                }],
            }

    result = AgentLoop(
        provider=EndlessProvider(),
        tool_executor=lambda name, arguments: (_ for _ in ()).throw(
            RuntimeError("backend unavailable")
        ),
        max_steps=2,
    ).run("Do work")

    assert result["status"] == "max_steps"
    assert result["steps"] == 2
    session = AgentSession.from_dict(result["session"])
    assert session.messages[-1].result["code"] == "TOOL_EXECUTION_ERROR"


def test_agent_loop_recovers_after_tool_error_with_different_action():
    class RecoveryProvider(LLMProvider):
        def __init__(self):
            self.calls = 0

        def generate_response(self, messages, tools=None, system_prompt="", model=None):
            self.calls += 1
            if self.calls == 1:
                return {
                    "tool_calls": [{
                        "name": "bad_tool",
                        "arguments": {},
                        "id": "bad-call",
                    }],
                }
            return {"content": "Recovered after inspecting the error."}

    result = AgentLoop(
        provider=RecoveryProvider(),
        tool_executor=lambda name, arguments: {
            "status": "error",
            "code": "BACKEND_UNAVAILABLE",
            "message": "KiCad is not connected.",
        },
        max_steps=3,
    ).run("Inspect the board")

    assert result["status"] == "completed"
    assert result["steps"] == 2
    assert result["session"]["metadata"]["recovery_failures"]


def test_agent_loop_stops_repeated_identical_errors():
    class RepeatingProvider(LLMProvider):
        def generate_response(self, messages, tools=None, system_prompt="", model=None):
            return {
                "tool_calls": [{
                    "name": "bad_tool",
                    "arguments": {},
                    "id": "same-call",
                }],
            }

    result = AgentLoop(
        provider=RepeatingProvider(),
        tool_executor=lambda name, arguments: {
            "status": "error",
            "code": "BACKEND_UNAVAILABLE",
            "message": "KiCad is not connected.",
        },
        max_steps=10,
        max_recovery_attempts=2,
    ).run("Inspect the board")

    assert result["status"] == "recovery_exhausted"
    assert result["steps"] == 2


def test_agent_loop_cancels_before_next_provider_turn():
    class EndlessProvider(LLMProvider):
        def __init__(self):
            self.calls = 0

        def generate_response(self, messages, tools=None, system_prompt="", model=None):
            self.calls += 1
            return {
                "tool_calls": [{
                    "name": "inspect_pcb",
                    "arguments": {},
                    "id": f"call-{self.calls}",
                }],
            }

    provider = EndlessProvider()
    loop = AgentLoop(
        provider=provider,
        tool_executor=lambda name, arguments: {"status": "success"},
        max_steps=5,
    )
    loop.cancel()
    result = loop.run("Inspect the board")

    assert result["status"] == "cancelled"
    assert result["steps"] == 0
    assert provider.calls == 0


def test_agent_loop_records_provider_and_tool_events():
    trace = AgentTrace("Inspect")

    class Provider(LLMProvider):
        def generate_response(self, messages, tools=None, system_prompt="", model=None):
            return {"content": "complete"}

    result = AgentLoop(
        provider=Provider(),
        tool_executor=lambda name, arguments: {"status": "success"},
        trace=trace,
    ).run("Inspect")

    assert result["status"] == "completed"
    trace.finish(True)
    event_types = [event.event_type for event in trace.events]
    assert "LLM_SESSION_START" in event_types
    assert "LLM_PROVIDER_CALL" in event_types
    assert "LLM_PROVIDER_RESULT" in event_types
    assert "LLM_SESSION_END" in event_types


def test_agent_loop_requires_final_verification_when_configured():
    class Provider(LLMProvider):
        def generate_response(self, messages, tools=None, system_prompt="", model=None):
            return {"content": "The requested change is complete."}

    result = AgentLoop(
        provider=Provider(),
        tool_executor=lambda name, arguments: {"status": "success"},
        final_verifier=lambda session: {
            "passed": False,
            "code": "GOAL_NOT_MET",
            "message": "The requested component is missing.",
        },
    ).run("Add R1")

    assert result["status"] == "final_verification_failed"
    assert result["session"]["metadata"]["final_verification"]["code"] == "GOAL_NOT_MET"


def test_agent_loop_completes_after_final_verification():
    class Provider(LLMProvider):
        def generate_response(self, messages, tools=None, system_prompt="", model=None):
            return {"content": "The board is ready."}

    result = AgentLoop(
        provider=Provider(),
        tool_executor=lambda name, arguments: {"status": "success"},
        final_verifier=lambda session: {
            "passed": True,
            "message": "All acceptance criteria passed.",
        },
    ).run("Inspect the board")

    assert result["status"] == "completed"
    assert result["session"]["metadata"]["final_verification"]["passed"] is True


def test_agent_loop_cancels_before_tool_execution():
    class ToolProvider(LLMProvider):
        def generate_response(self, messages, tools=None, system_prompt="", model=None):
            return {
                "tool_calls": [{
                    "name": "inspect_pcb",
                    "arguments": {},
                    "id": "call-1",
                }],
            }

    executed = []
    loop = AgentLoop(
        provider=ToolProvider(),
        tool_executor=lambda name, arguments: executed.append(name) or {
            "status": "success"
        },
        max_steps=5,
    )

    original = loop._execute_tool
    loop._execute_tool = lambda call: (
        loop.cancel() or original(call)
    )
    result = loop.run("Inspect the board")

    assert result["status"] == "cancelled"
    assert executed == ["inspect_pcb"]


def test_agent_loop_pauses_when_tool_requires_approval():
    class ApprovalProvider(LLMProvider):
        def generate_response(self, messages, tools=None, system_prompt="", model=None):
            return {
                "tool_calls": [{
                    "name": "remove_footprint",
                    "arguments": {"reference": "R1"},
                    "id": "call-approval",
                }],
            }

    result = AgentLoop(
        provider=ApprovalProvider(),
        tool_executor=lambda name, arguments: {
            "status": "approval_required",
            "code": "APPROVAL_REQUIRED",
        },
        max_steps=3,
    ).run("Remove R1")

    assert result["status"] == "waiting_approval"
    assert result["steps"] == 1


def test_agent_loop_approval_resumes_same_session():
    class ApprovalProvider(LLMProvider):
        def __init__(self):
            self.calls = 0

        def generate_response(self, messages, tools=None, system_prompt="", model=None):
            self.calls += 1
            if self.calls == 1:
                return {
                    "tool_calls": [{
                        "name": "remove_footprint",
                        "arguments": {"reference": "R1"},
                        "id": "call-approval",
                    }],
                }
            return {"content": "Removal completed."}

    normal = lambda name, arguments: {
        "status": "approval_required",
        "code": "APPROVAL_REQUIRED",
    }
    approved = lambda name, arguments: {
        "status": "success",
        "data": {"removed": arguments["reference"]},
    }
    loop = AgentLoop(
        provider=ApprovalProvider(),
        tool_executor=normal,
        approval_executor=approved,
        max_steps=3,
    )
    paused = loop.run("Remove R1")
    resumed = loop.resume_approval(
        AgentSession.from_dict(paused["session"]),
        approved=True,
    )

    assert resumed["status"] == "completed"
    assert resumed["steps"] == 2
    assert resumed["session"]["messages"][-2]["result"]["status"] == "success"
