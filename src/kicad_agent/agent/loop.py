"""Provider-neutral iterative LLM/tool execution loop."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Optional

from ..core.session import AgentSession, MessageType, SessionMessage
from ..providers.llm import LLMProvider
from .observability import AgentTrace


@dataclass
class NormalizedToolCall:
    """Provider-independent tool call extracted from an LLM response."""

    name: str
    arguments: Dict[str, Any]
    call_id: str


@dataclass
class NormalizedResponse:
    """Provider-independent assistant response."""

    content: str
    tool_calls: List[NormalizedToolCall]
    raw: Any = None


class AgentLoop:
    """Run an iterative assistant -> tool -> result conversation."""

    def __init__(
        self,
        provider: LLMProvider,
        tool_executor: Callable[[str, Dict[str, Any]], Dict[str, Any]],
        tool_schemas: Optional[List[Dict[str, Any]]] = None,
        max_steps: int = 20,
        system_prompt: str = "",
        approval_executor: Optional[
            Callable[[str, Dict[str, Any]], Dict[str, Any]]
        ] = None,
        max_recovery_attempts: int = 3,
        trace: Optional[AgentTrace] = None,
        final_verifier: Optional[
            Callable[[AgentSession], Dict[str, Any]]
        ] = None,
    ):
        if max_steps < 1:
            raise ValueError("max_steps must be at least 1")
        if max_recovery_attempts < 1:
            raise ValueError("max_recovery_attempts must be at least 1")
        self.provider = provider
        self.tool_executor = tool_executor
        self.tool_schemas = tool_schemas or []
        self.max_steps = max_steps
        self.system_prompt = system_prompt
        self.approval_executor = approval_executor
        self.max_recovery_attempts = max_recovery_attempts
        self._cancel_requested = False
        self.trace = trace
        self.final_verifier = final_verifier

    def cancel(self) -> None:
        """Request cooperative cancellation before the next provider/tool turn."""
        self._cancel_requested = True

    def run(
        self,
        user_request: str,
        domain: str = "pcb",
        session: Optional[AgentSession] = None,
    ) -> Dict[str, Any]:
        """Continue a session until completion, error, or the step limit."""
        active_session = session or AgentSession(
            user_request=user_request,
            domain=domain,
        )
        if not active_session.user_request:
            active_session.user_request = user_request
        active_session.domain = domain
        if not active_session.messages:
            active_session.append(SessionMessage.user(user_request, domain=domain))
        active_session.status = "running"
        self._record(
            "LLM_SESSION_START",
            f"Starting provider loop for domain '{domain}'.",
            {"session_id": active_session.session_id},
        )

        return self._run_steps(active_session, start_step=0)

    def resume_approval(
        self,
        session: AgentSession,
        approved: bool,
    ) -> Dict[str, Any]:
        """Resolve the newest approval request and continue the same session."""
        if session.status != "waiting_approval":
            raise ValueError("Session is not waiting for approval.")
        approval_result = next(
            (
                message
                for message in reversed(session.messages)
                if message.message_type is MessageType.TOOL_RESULT
                and (message.result or {}).get("status") == "approval_required"
            ),
            None,
        )
        if approval_result is None or not approval_result.tool_call_id:
            raise ValueError("Session has no pending approval request.")
        tool_call = next(
            (
                message
                for message in reversed(session.messages)
                if message.message_type is MessageType.TOOL_CALL
                and message.tool_call_id == approval_result.tool_call_id
            ),
            None,
        )
        if tool_call is None or not tool_call.tool_name:
            raise ValueError("Pending approval has no matching tool call.")

        if approved:
            if self.approval_executor is None:
                raise ValueError("No approved-tool executor is configured.")
            result = self._execute_with(
                self.approval_executor,
                tool_call.tool_name,
                tool_call.arguments,
            )
        else:
            result = {
                "status": "error",
                "code": "PERMISSION_DENIED",
                "message": "User denied approval for this tool call.",
            }
        session.append(
            SessionMessage.tool_result(
                tool_call.tool_name,
                result,
                tool_call_id=tool_call.tool_call_id,
                approval="approved" if approved else "denied",
            )
        )
        session.status = "running"
        return self._run_steps(
            session,
            start_step=int(session.metadata.get("steps", 0)),
        )

    def _run_steps(self, active_session: AgentSession, start_step: int) -> Dict[str, Any]:
        assistant_text = ""
        for step in range(start_step + 1, self.max_steps + 1):
            if self._cancel_requested:
                active_session.status = "cancelled"
                active_session.metadata["cancelled_at_step"] = step
                self._record("LLM_CANCELLED", "Loop cancelled before provider turn.", {"step": step})
                return self._result(active_session, assistant_text, step - 1)
            self._record(
                "LLM_PROVIDER_CALL",
                f"Calling provider at step {step}.",
                {"step": step, "message_count": len(active_session.messages)},
            )
            active_session.compact()
            response = self.provider.generate_response(
                messages=self._provider_messages(active_session),
                tools=self.tool_schemas,
                system_prompt=self.system_prompt,
            )
            normalized = self._normalize_response(response, step)
            assistant_text = normalized.content
            self._record(
                "LLM_PROVIDER_RESULT",
                f"Provider returned {len(normalized.tool_calls)} tool call(s).",
                {"step": step, "tool_call_count": len(normalized.tool_calls)},
            )

            for call in normalized.tool_calls:
                if self._cancel_requested:
                    active_session.status = "cancelled"
                    active_session.metadata["cancelled_at_step"] = step
                    self._record("LLM_CANCELLED", "Loop cancelled before tool execution.", {"step": step})
                    return self._result(active_session, normalized.content, step)
                self._record(
                    "LLM_TOOL_CALL",
                    f"Executing tool '{call.name}'.",
                    {"step": step, "tool": call.name, "call_id": call.call_id},
                )
                active_session.append(
                    SessionMessage.assistant(
                        content=normalized.content,
                        tool_name=call.name,
                        arguments=call.arguments,
                        tool_call_id=call.call_id,
                        step=step,
                    )
                )
                result = self._execute_tool(call)
                active_session.append(
                    SessionMessage.tool_result(
                        call.name,
                        result,
                        tool_call_id=call.call_id,
                        step=step,
                    )
                )
                self._record(
                    "LLM_TOOL_RESULT",
                    f"Tool '{call.name}' returned {result.get('status', 'unknown')}.",
                    {
                        "step": step,
                        "tool": call.name,
                        "call_id": call.call_id,
                        "status": result.get("status"),
                        "code": result.get("code"),
                    },
                )
                if result.get("status") == "approval_required":
                    active_session.status = "waiting_approval"
                    self._record("LLM_APPROVAL_REQUIRED", f"Approval required for '{call.name}'.", {"step": step})
                    return self._result(active_session, normalized.content, step)
                if result.get("status") == "error":
                    if self._record_recovery_failure(active_session, call, result):
                        active_session.status = "recovery_exhausted"
                        self._record(
                            "LLM_RECOVERY_EXHAUSTED",
                            f"Recovery exhausted for '{call.name}'.",
                            {"step": step, "code": result.get("code")},
                        )
                        return self._result(active_session, normalized.content, step)
                    self._record(
                        "LLM_RECOVERY_ATTEMPT",
                        f"Returning '{call.name}' error to provider.",
                        {"step": step, "code": result.get("code")},
                    )

            if not normalized.tool_calls:
                active_session.append(
                    SessionMessage.assistant(
                        content=normalized.content,
                        step=step,
                    )
                )
                if self.final_verifier is not None:
                    verification = self._verify_final(active_session)
                    active_session.metadata["final_verification"] = verification
                    if not verification.get("passed", False):
                        active_session.status = "final_verification_failed"
                        self._record(
                            "LLM_FINAL_VERIFICATION_FAILED",
                            verification.get("message", "Final verification failed."),
                            {"step": step},
                        )
                        return self._result(
                            active_session,
                            normalized.content,
                            step,
                        )
                active_session.status = "completed"
                self._record("LLM_SESSION_END", "Provider loop completed.", {"step": step})
                return self._result(active_session, assistant_text, step)

        active_session.status = "max_steps"
        self._record("LLM_MAX_STEPS", "Provider loop reached its step limit.", {"steps": self.max_steps})
        return self._result(active_session, assistant_text, self.max_steps)

    def _verify_final(self, session: AgentSession) -> Dict[str, Any]:
        try:
            result = self.final_verifier(session)
            if not isinstance(result, dict):
                return {
                    "passed": False,
                    "code": "INVALID_FINAL_VERIFICATION",
                    "message": "Final verifier must return a dictionary.",
                }
            return result
        except Exception as exc:
            return {
                "passed": False,
                "code": "FINAL_VERIFICATION_ERROR",
                "message": str(exc),
            }

    def _record(
        self,
        event_type: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        if self.trace is not None:
            self.trace.record(event_type, message, details)

    def _record_recovery_failure(
        self,
        session: AgentSession,
        call: NormalizedToolCall,
        result: Dict[str, Any],
    ) -> bool:
        """Record an error and return whether identical recovery is exhausted."""
        failures = session.metadata.setdefault("recovery_failures", {})
        signature = self._failure_signature(call, result)
        failures[signature] = int(failures.get(signature, 0)) + 1
        return failures[signature] >= self.max_recovery_attempts

    @staticmethod
    def _failure_signature(
        call: NormalizedToolCall,
        result: Dict[str, Any],
    ) -> str:
        import json

        return json.dumps(
            {
                "tool": call.name,
                "arguments": call.arguments,
                "code": result.get("code"),
                "message": result.get("message"),
            },
            sort_keys=True,
            default=str,
        )

    def _execute_tool(self, call: NormalizedToolCall) -> Dict[str, Any]:
        return self._execute_with(self.tool_executor, call.name, call.arguments)

    @staticmethod
    def _execute_with(
        executor: Callable[[str, Dict[str, Any]], Dict[str, Any]],
        name: str,
        arguments: Dict[str, Any],
    ) -> Dict[str, Any]:
        try:
            result = executor(name, arguments)
            if isinstance(result, dict):
                return result
            return {
                "status": "error",
                "code": "INVALID_TOOL_RESULT",
                "message": "Tool executor must return a dictionary.",
            }
        except Exception as exc:
            return {
                "status": "error",
                "code": "TOOL_EXECUTION_ERROR",
                "message": str(exc),
            }

    @staticmethod
    def _result(
        session: AgentSession,
        assistant_text: str,
        steps: int,
    ) -> Dict[str, Any]:
        session.metadata["steps"] = steps
        return {
            "status": session.status,
            "session_id": session.session_id,
            "content": assistant_text,
            "steps": steps,
            "session": session.to_dict(),
        }

    @staticmethod
    def _provider_messages(session: AgentSession) -> List[Dict[str, Any]]:
        """Convert normalized session events to common chat message shapes."""
        messages: List[Dict[str, Any]] = []
        for message in session.messages:
            if message.message_type in (
                MessageType.SYSTEM,
                MessageType.USER,
                MessageType.ASSISTANT,
            ):
                messages.append({
                    "role": message.role.value,
                    "content": message.content,
                })
            elif message.message_type is MessageType.TOOL_CALL:
                messages.append({
                    "role": "assistant",
                    "content": [{
                        "type": "tool_use",
                        "id": message.tool_call_id,
                        "name": message.tool_name,
                        "input": message.arguments,
                    }],
                })
            elif message.message_type is MessageType.TOOL_RESULT:
                messages.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": message.tool_call_id,
                        "content": message.result or {},
                    }],
                })
        return messages

    @classmethod
    def _normalize_response(cls, response: Any, step: int) -> NormalizedResponse:
        if isinstance(response, str):
            return NormalizedResponse(content=response, tool_calls=[], raw=response)

        if isinstance(response, dict):
            content = str(response.get("content", "") or "")
            raw_calls = response.get("tool_calls", [])
            return NormalizedResponse(
                content=content,
                tool_calls=cls._normalize_dict_calls(raw_calls, step),
                raw=response,
            )

        blocks = getattr(response, "content", None)
        if blocks is None:
            return NormalizedResponse(
                content=str(response),
                tool_calls=[],
                raw=response,
            )

        text_parts: List[str] = []
        calls: List[NormalizedToolCall] = []
        for index, block in enumerate(blocks):
            block_type = cls._value(block, "type")
            if block_type == "text":
                text_parts.append(str(cls._value(block, "text") or ""))
            elif block_type == "tool_use":
                calls.append(
                    NormalizedToolCall(
                        name=str(cls._value(block, "name") or ""),
                        arguments=dict(cls._value(block, "input") or {}),
                        call_id=str(
                            cls._value(block, "id")
                            or f"step-{step}-tool-{index}"
                        ),
                    )
                )
        return NormalizedResponse(
            content="".join(text_parts),
            tool_calls=[call for call in calls if call.name],
            raw=response,
        )

    @staticmethod
    def _normalize_dict_calls(
        raw_calls: Iterable[Any],
        step: int,
    ) -> List[NormalizedToolCall]:
        calls: List[NormalizedToolCall] = []
        for index, raw_call in enumerate(raw_calls):
            if not isinstance(raw_call, dict):
                continue
            function = raw_call.get("function", raw_call)
            name = function.get("name") or function.get("tool_name")
            arguments = function.get("arguments", function.get("input", {}))
            if isinstance(arguments, str):
                import json

                try:
                    arguments = json.loads(arguments)
                except json.JSONDecodeError:
                    arguments = {}
            if name:
                calls.append(
                    NormalizedToolCall(
                        name=str(name),
                        arguments=dict(arguments or {}),
                        call_id=str(
                            raw_call.get("id")
                            or function.get("id")
                            or f"step-{step}-tool-{index}"
                        ),
                    )
                )
        return calls

    @staticmethod
    def _value(obj: Any, name: str) -> Any:
        if isinstance(obj, dict):
            return obj.get(name)
        return getattr(obj, name, None)
