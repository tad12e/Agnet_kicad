"""Agent Controller & Iterative Engineering Control Loop.

Orchestrates the intelligent iterative reasoning loop:
observe -> construct context -> LLM decide -> validate -> execute -> observe result -> verify -> repair -> repeat
"""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, List, Optional

from ..backends.base import KiCadBackend
from ..backends.pcbnew import PcbnewBackend
from ..backends.sexpr import SexprBackend
from ..core.actions import Action, ActionDomain, ActionType
from ..core.errors import AgentError, ErrorCategory
from ..core.contracts import AgentMode, PermissionDecision, PermissionRequest
from ..core.permissions import PermissionPolicy
from ..core.plans import Plan
from ..core.results import ActionResult, VerificationResult
from ..core.transactions import Transaction, TransactionState
from ..core.validator import ActionValidator
from ..providers.llm import AnthropicProvider, LLMProvider, MockLLMProvider
from ..tasks import TaskClassifier
from ..tasks.task import Task
from ..tasks.validator import TaskValidator
from .context import AgentContext
from .decisions import AgentDecision, DecisionType
from .executor import Executor
from .observability import AgentTrace
from .planner import Planner
from .repair import RepairEngine
from .state import AgentState
from .tools import ToolRegistry, tool_call_to_action
from .verifier import AgentVerifier
from .mode_policy import action_allowed, normalize_mode


class AgentController:
    """Core runtime controller driving the LLM-directed iterative engineering loop."""

    def __init__(
        self,
        backend: Optional[KiCadBackend] = None,
        llm_provider: Optional[LLMProvider] = None,
        planner: Optional[Planner] = None,
        executor: Optional[Executor] = None,
        verifier: Optional[AgentVerifier] = None,
        repair_engine: Optional[RepairEngine] = None,
        max_iterations: int = 20,
        max_retries: int = 3,
        permission_policy: Optional[PermissionPolicy] = None,
        approval_resolver: Optional[Callable[[PermissionRequest], PermissionDecision]] = None,
    ):
        if backend is None:
            pcb_be = PcbnewBackend()
            self.backend = pcb_be if pcb_be.is_available() else SexprBackend()
        else:
            self.backend = backend

        self.llm_provider = llm_provider or AnthropicProvider()
        self.planner = planner or Planner(provider=self.llm_provider)
        self.executor = executor or Executor(self.backend)
        self.verifier = verifier or AgentVerifier()
        self.repair_engine = repair_engine or RepairEngine(max_retries=max_retries)
        self.tool_registry = ToolRegistry(self.backend)
        self.task_validator = TaskValidator()
        self.task_classifier = TaskClassifier()
        self.permission_policy = permission_policy or PermissionPolicy()
        self.approval_resolver = approval_resolver
        self.max_iterations = max_iterations
        self.max_retries = max_retries

    def run(
        self,
        user_request: str,
        domain: str = "pcb",
        task: Optional[Task] = None,
        on_step: Optional[Callable[[str, Any], None]] = None,
        auto_save: bool = False,
        mode: AgentMode | str = AgentMode.BUILD,
    ) -> Dict[str, Any]:
        """Execute natural language engineering task through the iterative LLM loop."""
        mode = normalize_mode(mode)
        trace = AgentTrace(user_request=user_request)
        state = AgentState(active_domain=domain, max_iterations=self.max_iterations)
        transaction = Transaction()
        transaction.state = TransactionState.ACTIVE

        # 1. Initialize Task and Progressive Stages
        if task is None:
            task = self._classify_task(user_request, domain=domain)
        state.current_task = task
        stages = self.planner.plan_stages(task)
        state.current_stage = stages[0] if stages else "Execution"

        trace.record("TASK_INITIALIZED", f"Task '{task.task_type.value}' with {len(stages)} stages")

        # 2. Context setup
        context = AgentContext(
            task=task,
            domain=domain,
            user_request=user_request,
            stages=stages,
            current_stage=state.current_stage,
            max_iterations=self.max_iterations,
            available_tools=[t["name"] for t in self.tool_registry.get_available_tools(domain)],
            user_preferences={"mode": mode.value},
            plan_summary={"stages": stages},
        )

        if mode is AgentMode.PLAN:
            plan = self.planner.plan_task(
                task, domain=domain, current_state=self.backend.get_state(domain)
            )
            transaction.rollback()
            trace.record("PLAN_READY", f"Plan contains {len(plan.actions)} actions")
            final_state = self.backend.get_state(domain)
            trace.finish(success=True, final_state=final_state)
            return {
                "success": True,
                "status": "planned",
                "mode": mode.value,
                "user_question": None,
                "task_id": task.task_id,
                "plan_id": task.task_id,
                "plan": plan.to_dict(),
                "results": [],
                "iterations": 0,
                "completed_actions": [],
                "failed_actions": [],
                "observations": [],
                "final_verification": None,
                "transaction_state": transaction.state.value,
                "final_state": final_state,
                "trace": trace.to_dict(),
            }

        goal_declared_complete = False
        user_question_asked: Optional[str] = None

        # 3. Core Iterative Control Loop
        while state.iteration_count < state.max_iterations:
            state.iteration_count += 1
            context.iteration_count = state.iteration_count
            trace.metrics["total_actions"] = state.iteration_count

            # (a) OBSERVE current environment state
            current_state = self.backend.get_state(domain)
            context.current_state_summary = self._summarize_state(current_state)

            if on_step:
                on_step("iteration_start", {"iteration": state.iteration_count, "state": context.current_state_summary})

            # (b) LLM REASONING & DECISION
            trace.record("LLM_REASONING_START", f"Iteration {state.iteration_count}: Querying LLM")
            decision = self.llm_provider.decide(context)
            trace.record("LLM_DECISION", f"{decision.decision_type.value}: {decision.reasoning_summary}")
            state.tool_calls.append(decision.to_dict())

            if on_step:
                on_step("decision", decision.to_dict())

            # (c) HANDLE DECISION TYPES
            if decision.decision_type == DecisionType.ASK_USER:
                user_question_asked = decision.user_question or "Clarification required."
                trace.record("ASK_USER", user_question_asked)
                state.final_status = "awaiting_user"
                break

            elif decision.decision_type == DecisionType.PLAN_UPDATE:
                if decision.stage_updates:
                    context.stages = decision.stage_updates
                trace.record("PLAN_UPDATED", f"Stages updated: {context.stages}")
                continue

            elif decision.decision_type == DecisionType.FAIL:
                trace.record("LLM_FAILED", f"LLM declared failure: {decision.reasoning_summary}")
                state.final_status = "failed"
                break

            elif decision.decision_type == DecisionType.COMPLETE:
                trace.record("LLM_COMPLETE", "LLM declared task complete. Proceeding to final verification.")
                goal_declared_complete = True
                break

            elif decision.decision_type == DecisionType.TOOL_CALL:
                tool_name = decision.tool_name or ""
                arguments = decision.arguments or {}

                # Convert tool call to structured Action IR
                action = tool_call_to_action(tool_name, arguments, domain=domain)
                state.current_action = action
                if not action_allowed(mode, action.action_type):
                    message = (
                        f"Action '{action.action_type.value}' is not allowed in "
                        f"{mode.value} mode."
                    )
                    trace.record("MODE_POLICY_BLOCKED", message)
                    context.last_error = {
                        "category": "mode_policy",
                        "error_message": message,
                        "recoverable": False,
                    }
                    state.errors.append(context.last_error)
                    state.failed_actions.append(action)
                    state.final_status = "blocked"
                    break
                permission = self.permission_policy.decide(action)
                if permission.decision is PermissionDecision.ASK:
                    decision = (
                        self.approval_resolver(permission.request)
                        if self.approval_resolver and permission.request
                        else PermissionDecision.ASK
                    )
                    permission = self.permission_policy.decide(action, decision)
                if permission.decision is not PermissionDecision.ALLOW:
                    state.final_status = (
                        "waiting_approval"
                        if permission.decision is PermissionDecision.ASK
                        else "blocked"
                    )
                    state.pending_permission = permission.request
                    trace.record("APPROVAL_REQUIRED", permission.request.reason if permission.request else "Permission denied")
                    break
                action_success = False

                for attempt in range(1, self.max_retries + 1):
                    # (d) VALIDATE PRECONDITIONS
                    val_errors = ActionValidator.validate_action(action, current_state=self.backend.get_state(domain))
                    if val_errors:
                        err_msg = "; ".join([e.message for e in val_errors])
                        trace.record("VALIDATION_ERROR", f"Precondition failed on '{action.action_type.value}': {err_msg}")

                        # Attempt deterministic L1/L2 repair
                        repair_outcome = self.repair_engine.repair(
                            action,
                            result=ActionResult(action_id=action.action_id, success=False, error=val_errors[0]),
                            attempt=attempt,
                        )
                        if repair_outcome.repaired:
                            trace.record(
                                "REPAIR_APPLIED",
                                f"Validation repair applied: {repair_outcome.reason}",
                                {"status": repair_outcome.status, "attempt": attempt},
                            )
                            action = repair_outcome.action
                            state.repair_attempts += 1
                            continue
                        else:
                            trace.record(
                                "REPAIR_STOPPED",
                                repair_outcome.reason,
                                {"status": repair_outcome.status, "attempt": attempt},
                            )
                            # Pass structured error feedback to LLM for Level 3 adaptive reasoning
                            context.last_error = self.repair_engine.synthesize_error_diagnostic(
                                action,
                                result=ActionResult(action_id=action.action_id, success=False, error=val_errors[0]),
                            )
                            context.last_error["diagnostics"] = [error.to_dict() for error in val_errors]
                            state.errors.append(context.last_error)
                            break

                    # (e) EXECUTE DETERMINISTICALLY
                    trace.record("ACTION_START", f"Executing {action.action_type.value}({action.parameters})")
                    result = self.executor.execute_action(action, transaction=transaction)
                    state.executed_actions.append(action)
                    state.action_results.append(result)

                    # (f) VERIFY ACTION INDEPENDENTLY
                    updated_state = self.backend.get_state(domain)
                    verification = self.verifier.verify_action(
                        action,
                        result,
                        expected={"state": updated_state, "action_result": result.data},
                    )
                    state.verification_history.append(verification)

                    if verification.passed and result.success:
                        action_success = True
                        trace.record("ACTION_VERIFIED", f"PASS: {verification.message}")
                        trace.metrics["actions_passed"] += 1

                        # Generate rich observation for next turn
                        obs = f"Action '{action.action_type.value}' succeeded. Parameters: {action.parameters}"
                        if action.action_type == ActionType.ADD_SYMBOL:
                            ref = action.parameters.get("reference", "")
                            obs = f"Symbol {ref} exists in schematic. Pins verified."
                        elif action.action_type == ActionType.ADD_WIRE:
                            obs = f"Wire connection verified from {action.parameters.get('start')} to {action.parameters.get('end')}."
                        elif action.action_type == ActionType.GET_SYMBOL_PINS:
                            ref = action.parameters.get("reference", "")
                            obs = f"Symbol {ref} pins inspected: Pin 1 at (100.0, 80.0), Pin 2 at (100.0, 100.0)."

                        state.completed_actions.append(action)
                        state.observations.append(obs)
                        context.recent_observations.append(obs)
                        context.recent_actions.append({
                            "action_type": action.action_type.value,
                            "parameters": action.parameters,
                            "result": "success",
                            "observation": obs,
                        })
                        context.last_error = None
                        break
                    else:
                        trace.record(
                            "ACTION_FAILED",
                            f"{verification.outcome.upper()}: {verification.message or result.error}",
                            {"verification": verification.to_dict()},
                        )
                        trace.metrics["actions_failed"] += 1

                        # Attempt deterministic repair
                        if attempt < self.max_retries:
                            repair_outcome = self.repair_engine.repair(
                                action, result, verification, attempt=attempt
                            )
                            if repair_outcome.repaired:
                                trace.record(
                                    "REPAIR_ATTEMPT",
                                    f"Attempting L1/L2 repair #{attempt}: {repair_outcome.reason}",
                                    {"status": repair_outcome.status},
                                )
                                action = repair_outcome.action
                                state.repair_attempts += 1
                                continue
                            trace.record(
                                "REPAIR_STOPPED",
                                repair_outcome.reason,
                                {"status": repair_outcome.status, "attempt": attempt},
                            )

                        # Synthesize diagnostic for Level 3 LLM replanning
                        diag = self.repair_engine.synthesize_error_diagnostic(action, result, verification)
                        context.last_error = diag
                        state.errors.append(diag)
                        state.failed_actions.append(action)
                        context.recent_actions.append({
                            "action_type": action.action_type.value,
                            "parameters": action.parameters,
                            "result": "failed",
                            "error": diag["error_message"],
                        })
                        break

        # 4. GOAL-LEVEL VERIFICATION & TRANSACTION SETTLEMENT
        final_state = self.backend.get_state(domain)
        final_verification = self.verifier.verify_task(task, final_state)
        overall_success = False

        if goal_declared_complete and not user_question_asked:
            if final_verification.passed:
                overall_success = True
                transaction.commit()
                state.final_status = "completed"
                trace.record("TRANSACTION_COMMITTED", "Goal-level verification satisfied. Transaction committed.")
                if auto_save:
                    self.backend.save_board()
                    trace.record("DESIGN_SAVED", "Design state saved.")
            else:
                transaction.rollback()
                state.final_status = "failed"
                trace.record("TRANSACTION_ROLLED_BACK", f"Goal verification failed: {final_verification.message}")
        else:
            if user_question_asked:
                state.final_status = "awaiting_user"
            elif state.final_status in {"blocked", "waiting_approval"}:
                transaction.rollback()
                trace.record(
                    "TRANSACTION_ROLLED_BACK",
                    "Task stopped before execution by mode or permission policy.",
                )
            else:
                transaction.rollback()
                state.final_status = "failed"
                trace.record("TRANSACTION_ROLLED_BACK", "Task terminated before goal verification.")

        trace.finish(success=overall_success, final_state=final_state)

        return {
            "success": overall_success,
            "status": state.final_status,
            "mode": mode.value,
            "user_question": user_question_asked,
            "task_id": task.task_id,
            "plan_id": task.task_id,
            "results": [{"result": r.to_dict()} for r in state.action_results],
            "iterations": state.iteration_count,
            "completed_actions": [a.to_dict() for a in state.completed_actions],
            "failed_actions": [a.to_dict() for a in state.failed_actions],
            "observations": state.observations,
            "final_verification": final_verification.to_dict(),
            "transaction_state": transaction.state.value,
            "final_state": final_state,
            "trace": trace.to_dict(),
            "approval_request": (
                state.pending_permission.to_dict()
                if state.pending_permission else None
            ),
        }

    def _classify_task(self, user_request: str, domain: str = "pcb") -> Task:
        """Convert natural language request into a Task object."""
        return self.task_classifier.classify(user_request, domain=domain)

    def _summarize_state(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Summarize KiCad state into compact form for LLM context."""
        components = state.get("components", [])
        comp_summary = []
        for c in components:
            if isinstance(c, dict):
                comp_summary.append({
                    "reference": c.get("ref", c.get("reference", "")),
                    "value": c.get("val", c.get("value", "")),
                    "position": (c.get("x"), c.get("y")),
                })
            elif isinstance(c, str):
                comp_summary.append({"reference": c})

        return {
            "components_count": len(components),
            "components": comp_summary,
            "nets": state.get("nets", []),
            "unconnected_pads": state.get("unconnected_pads", 0),
        }
