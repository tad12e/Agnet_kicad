"""Top-level KiCad AI Agent Orchestrator.

Manages the complete lifecycle:
observe -> plan -> validate -> execute -> verify -> repair -> retry -> finalize
"""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, List, Optional

from ..backends.base import KiCadBackend
from ..backends.ipc import IPCBackend
from ..backends.pcbnew import PcbnewBackend
from ..backends.sexpr import SexprBackend
from ..core.actions import Action, ActionType
from ..core.errors import AgentError, ErrorCategory
from ..core.goals import Goal
from ..core.plans import Plan
from ..core.results import ActionResult, VerificationResult
from ..core.session import AgentSession, SessionMessage
from ..core.session_store import SessionStore
from ..core.permissions import PermissionPolicy
from ..core.transactions import Transaction
from ..core.validator import ActionValidator
from .context import AgentContext
from .error_analyzer import ErrorAnalyzer
from .executor import Executor
from .loop import AgentLoop
from .observability import AgentTrace
from .planner import Planner
from .repair import RepairEngine
from .state import AgentState
from .tools import ToolRegistry
from .verifier import AgentVerifier
from ..providers.factory import configured_provider
from ..providers.llm import LLMProvider


class KiCadAgent:
    """Top-level agent orchestrator for KiCad automation."""

    def __init__(
        self,
        backend: Optional[KiCadBackend] = None,
        planner: Optional[Planner] = None,
        executor: Optional[Executor] = None,
        verifier: Optional[AgentVerifier] = None,
        repair_engine: Optional[RepairEngine] = None,
        max_retries: int = 3,
        fallback: Optional[KiCadBackend] = None,
        provider: Optional[LLMProvider] = None,
        session_store: Optional[SessionStore] = None,
    ):
        # Default to PcbnewBackend if available, else SexprBackend fallback
        if backend is None:
            pcb_be = PcbnewBackend()
            self.backend = pcb_be if pcb_be.is_available() else SexprBackend()
        else:
            self.backend = backend

        # Part 9 (L4): an IPCBackend without its own fallback adopts the
        # agent-level one, so schematic actions fail over instead of dying
        # on refused live commits. No file is ever guessed: the caller must
        # supply a file-targeted fallback (e.g. SexprBackend(sch_filepath)).
        if (fallback is not None and isinstance(self.backend, IPCBackend)
                and self.backend.fallback is None):
            self.backend.fallback = fallback

        self.provider = configured_provider(provider)
        self.planner = planner or Planner(provider=self.provider)
        self.executor = executor or Executor(self.backend)
        self.verifier = verifier or AgentVerifier()
        self.repair_engine = repair_engine or RepairEngine(max_retries=max_retries)
        self.max_retries = max_retries
        self.session_store = session_store or SessionStore()
        self.tool_registry = ToolRegistry(self.backend)

        self.state = AgentState()
        self.context = AgentContext()
        self.context.session = self.state.session

    def run(
        self,
        user_request: str,
        domain: str = "pcb",
        on_step: Optional[Callable[[str, Any], None]] = None,
        auto_save: bool = False,
    ) -> Dict[str, Any]:
        """Execute a natural language user request through the agent lifecycle."""
        trace = AgentTrace(user_request=user_request)
        self.state.session.user_request = user_request
        self.state.session.domain = domain
        self.state.session.status = "running"
        self.context.append_message(SessionMessage.user(user_request, domain=domain))
        self.state.active_domain = domain
        self.state.iteration_count = 0

        # Step 1: OBSERVE current board state
        current_state = self.backend.get_state(domain)
        trace.record("STATE_INSPECTED", f"Initial board state: {len(current_state.get('components', []))} components, {len(current_state.get('nets', []))} nets")
        if on_step:
            on_step("planning", {"request": user_request, "state": current_state})

        # Step 2: PLAN
        plan = self.planner.plan_request(user_request, domain=domain, current_state=current_state)
        self.state.current_plan = plan
        trace.record("PLAN_CREATED", f"Plan generated with {len(plan.actions)} actions and {len(plan.goals)} goals")

        executed_results = []
        all_passed = True
        transaction = Transaction()
        checkpoint = self.backend.create_checkpoint(domain)
        transaction.set_checkpoint(
            checkpoint,
            (
                lambda: self.backend.restore_checkpoint(checkpoint)
                if checkpoint.get("rollback_supported")
                else None
            ),
            lambda: self.backend.discard_checkpoint(checkpoint),
        )

        for action in plan.actions:
            self.state.iteration_count += 1
            if self.state.iteration_count > self.state.max_iterations:
                trace.record("LIMIT_REACHED", "Iteration limit exceeded")
                break

            action_success = False
            current_action = action
            result: Optional[ActionResult] = None
            verification: Optional[VerificationResult] = None

            for attempt in range(1, self.max_retries + 1):
                trace.metrics["total_actions"] += 1
                if on_step:
                    on_step("executing_action", current_action.to_dict())

                # Step 3: VALIDATE preconditions
                val_errors = ActionValidator.validate_action(current_action, current_state=self.backend.get_state(domain))
                if val_errors:
                    err_msg = "; ".join([e.message for e in val_errors])
                    trace.record("VALIDATION_ERROR", f"Precondition failed on '{current_action.action_type.value}': {err_msg}")
                    # Attempt immediate repair of validation error
                    repaired = self.repair_engine.attempt_repair(
                        current_action,
                        result=ActionResult(action_id=current_action.action_id, success=False, error=val_errors[0]),
                        attempt=attempt,
                    )
                    if repaired:
                        trace.record("REPAIR_APPLIED", f"Validation repair: {repaired.description}")
                        current_action = repaired
                        trace.metrics["repairs_attempted"] += 1
                        continue
                    else:
                        break

                # Step 4: EXECUTE action deterministically
                trace.record("ACTION_START", f"Executing {current_action.action_type.value}({current_action.parameters})")
                result = self.executor.execute_action(current_action, transaction=transaction)
                self.state.executed_actions.append(current_action)
                self.state.action_results.append(result)

                # Step 5: VERIFY action independently
                # Pass updated board state to verifier for independent inspection
                updated_state = self.backend.get_state(domain)
                verification = self.verifier.verify_action(current_action, result, expected={"state": updated_state})
                self.state.verification_history.append(verification)

                if verification.passed and result.success:
                    trace.record("ACTION_VERIFIED", f"PASS: {verification.message}")
                    trace.metrics["actions_passed"] += 1
                    action_success = True
                    executed_results.append({
                        "action": current_action.to_dict(),
                        "result": result.to_dict(),
                        "verification": verification.to_dict(),
                    })
                    break
                else:
                    trace.record("ACTION_FAILED", f"FAIL: {verification.message or result.error}")
                    trace.metrics["actions_failed"] += 1
                    trace.metrics["retries"] += 1

                    # Step 6: ANALYZE ERROR & REPAIR (Part 9: ErrorAnalyzer
                    # categorizes verification-only failures so repair rules
                    # see a structured error instead of None).
                    if (result is not None and result.error is None
                            and verification is not None
                            and not verification.passed):
                        result.error = ErrorAnalyzer.analyze(
                            Exception(verification.message or "verification failed"),
                            operation=current_action.action_type.value,
                        )
                        trace.record("ERROR_ANALYZED",
                                     f"{result.error.category.value}: {result.error.message}")
                    if attempt < self.max_retries:
                        trace.metrics["repairs_attempted"] += 1
                        repaired = self.repair_engine.attempt_repair(current_action, result, verification, attempt=attempt)
                        if repaired:
                            trace.record("REPAIR_ATTEMPT", f"Attempting repair #{attempt}: {repaired.description}")
                            current_action = repaired
                        else:
                            trace.record("REPAIR_UNAVAILABLE", "No deterministic repair rule found")
                            break
                    else:
                        trace.record("MAX_RETRIES", f"Max retries ({self.max_retries}) reached for action {current_action.action_type.value}")

            if not action_success:
                all_passed = False
                executed_results.append({
                    "action": current_action.to_dict(),
                    "result": result.to_dict() if result else None,
                    "verification": verification.to_dict() if verification else None,
                    "failed": True,
                })
                break

        # Step 7: GLOBAL GOAL / INTENT VERIFICATION
        if all_passed:
            transaction.commit()
            trace.record("TRANSACTION_COMMITTED", "All actions verified, transaction committed")
            if auto_save:
                try:
                    self.backend.save_board()
                    trace.record("BOARD_SAVED", "Board saved successfully")
                except Exception as e:
                    trace.record("BOARD_SAVE_FAILED", f"Auto-save failed: {e}")
        else:
            rollback_succeeded = transaction.rollback()
            trace.record(
                "TRANSACTION_ROLLED_BACK",
                (
                    "Transaction checkpoint restored."
                    if rollback_succeeded and checkpoint.get("rollback_supported")
                    else "Rollback is unsupported for this backend."
                ),
            )

        final_state = self.backend.get_state(domain)
        self.state.session.status = "completed" if all_passed else "failed"
        trace.finish(success=all_passed, final_state=final_state)

        return {
            "success": all_passed,
            "plan_id": plan.plan_id,
            "results": executed_results,
            "transaction_state": transaction.state.value,
            "final_state": final_state,
            "trace": trace.to_dict(),
        }

    def run_llm(
        self,
        user_request: str,
        domain: str = "pcb",
        provider: Optional[LLMProvider] = None,
        max_steps: int = 20,
        system_prompt: str = "",
        session: Optional[AgentSession] = None,
        permission_policy: Optional[PermissionPolicy] = None,
        final_verifier: Optional[Callable[[AgentSession], Dict[str, Any]]] = None,
        goal: Optional[Goal] = None,
    ) -> Dict[str, Any]:
        """Run the opt-in iterative LLM/tool loop against this backend.

        The existing :meth:`run` method remains the deterministic planner
        path. This method is the migration seam for callers that want
        provider-driven tool selection and replanning.
        """
        active_provider = provider or self.provider
        if active_provider is None:
            raise ValueError(
                "An LLM provider is required for run_llm(); "
                "pass provider= or configure KiCadAgent(provider=...)."
            )

        active_session = session
        if active_session is None or (
            active_session.user_request
            and active_session.user_request != user_request
        ):
            active_session = AgentSession(
                user_request=user_request,
                domain=domain,
            )

        trace = AgentTrace(user_request=user_request)
        loop = self._create_llm_loop(
            active_provider,
            permission_policy=permission_policy,
            max_steps=max_steps,
            system_prompt=system_prompt,
            trace=trace,
            final_verifier=final_verifier,
            goal=goal,
            domain=domain,
        )
        result = loop.run(
            user_request=user_request,
            domain=domain,
            session=active_session,
        )
        self.state.session = active_session
        self.context.session = active_session
        self.context.conversation_history = [
            message.to_dict() for message in active_session.messages
        ]
        self.state.active_domain = domain
        self.state.iteration_count = result["steps"]
        self._llm_loop = loop
        trace.finish(
            success=result["status"] == "completed",
            final_state=self.backend.get_state(domain),
        )
        result["trace"] = trace.to_dict()
        return result

    def _create_llm_loop(
        self,
        provider: LLMProvider,
        permission_policy: Optional[PermissionPolicy],
        max_steps: int,
        system_prompt: str,
        trace: AgentTrace,
        final_verifier: Optional[Callable[[AgentSession], Dict[str, Any]]],
        goal: Optional[Goal],
        domain: str,
    ) -> AgentLoop:
        """Build a loop for both new and restored sessions."""
        execute_tool = lambda name, arguments: self._execute_llm_tool(
            name,
            arguments,
            permission_policy=permission_policy,
        )
        approved_tool = lambda name, arguments: self._execute_llm_tool(
            name,
            arguments,
            permission_policy=permission_policy,
            approved=True,
        )
        native_final_verifier = final_verifier
        if native_final_verifier is None and goal is not None:
            native_final_verifier = lambda active_session: (
                self._verify_llm_goal(goal, domain)
            )

        return AgentLoop(
            provider=provider,
            tool_executor=execute_tool,
            approval_executor=approved_tool,
            tool_schemas=self.tool_registry.get_available_tools(),
            max_steps=max_steps,
            system_prompt=system_prompt,
            trace=trace,
            final_verifier=native_final_verifier,
        )

    def _verify_llm_goal(self, goal: Goal, domain: str) -> Dict[str, Any]:
        """Evaluate a native goal against freshly observed backend state."""
        verification = self.verifier.verify_goal(
            goal,
            self.backend.get_state(domain),
        )
        return {
            "passed": verification.passed,
            "verifier_name": verification.verifier_name,
            "message": verification.message,
            "details": verification.details,
            "violations": verification.violations,
        }

    def _execute_llm_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        permission_policy: Optional[PermissionPolicy] = None,
        approved: bool = False,
    ) -> Dict[str, Any]:
        """Execute one model tool and independently verify mutations."""
        result = self.tool_registry.execute_guarded_tool(
            tool_name,
            arguments,
            permission_policy=permission_policy,
            approved=approved,
        )
        if result.get("status") != "success":
            return result

        action = self.tool_registry._action_for_tool(tool_name, arguments)
        if action is None:
            return result

        verification = self.verifier.verify_action(
            action,
            ActionResult(
                action_id=action.action_id,
                success=True,
                data=result.get("data", {}),
            ),
            expected={"state": self.backend.get_state(action.domain.value)},
        )
        result["verification"] = verification.to_dict()
        if not verification.passed:
            return {
                **result,
                "status": "error",
                "code": "TOOL_VERIFICATION_FAILED",
                "message": verification.message,
            }
        return result

    def resolve_llm_approval(
        self,
        approved: bool,
        session: Optional[AgentSession] = None,
    ) -> Dict[str, Any]:
        """Approve or deny the pending LLM tool call and resume the session."""
        loop = getattr(self, "_llm_loop", None)
        active_session = session or self.state.session
        if loop is None:
            raise ValueError("No active LLM loop is available.")
        result = loop.resume_approval(active_session, approved)
        self.state.session = active_session
        self.context.session = active_session
        self.context.conversation_history = [
            message.to_dict() for message in active_session.messages
        ]
        self.state.iteration_count = result["steps"]
        if isinstance(result, dict) and hasattr(loop, "trace") and loop.trace is not None:
            loop.trace.finish(
                success=result["status"] == "completed",
                final_state=self.backend.get_state(active_session.domain),
            )
            result["trace"] = loop.trace.to_dict()
        return result

    def save_llm_session(self, path: str) -> str:
        """Persist the active LLM conversation for later continuation."""
        return self.session_store.save(self.state.session, path)

    def load_llm_session(self, path: str) -> AgentSession:
        """Restore a saved LLM conversation into this agent instance."""
        session = self.session_store.load(path)
        self.state.session = session
        self.context.session = session
        self.context.conversation_history = [
            message.to_dict() for message in session.messages
        ]
        self.state.active_domain = session.domain
        self.state.iteration_count = int(session.metadata.get("steps", 0))
        if self.provider is not None:
            self._llm_loop = self._create_llm_loop(
                self.provider,
                permission_policy=None,
                max_steps=int(session.metadata.get("max_steps", 20)),
                system_prompt="",
                trace=AgentTrace(user_request=session.user_request),
                final_verifier=None,
                goal=None,
                domain=session.domain,
            )
        return session

    def cancel_llm(self) -> Dict[str, Any]:
        """Request cancellation of the active LLM loop."""
        loop = getattr(self, "_llm_loop", None)
        if loop is None:
            raise ValueError("No active LLM loop is available.")
        if self.state.session.status not in {"running", "waiting_approval"}:
            raise ValueError(
                f"LLM session is not active: {self.state.session.status}"
            )
        loop.cancel()
        self.state.session.status = "cancelled"
        return {
            "status": "cancelled",
            "session_id": self.state.session.session_id,
            "steps": int(self.state.session.metadata.get("steps", 0)),
        }
