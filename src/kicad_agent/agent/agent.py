"""Top-level KiCad AI Agent Orchestrator.

Manages the complete lifecycle:
observe -> plan -> validate -> execute -> verify -> repair -> retry -> finalize
"""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, List, Optional

from ..backends.base import KiCadBackend
from ..backends.pcbnew import PcbnewBackend
from ..backends.sexpr import SexprBackend
from ..core.actions import Action, ActionType
from ..core.errors import AgentError, ErrorCategory
from ..core.plans import Plan
from ..core.results import ActionResult, VerificationResult
from ..core.transactions import Transaction
from ..core.validator import ActionValidator
from .context import AgentContext
from .error_analyzer import ErrorAnalyzer
from .executor import Executor
from .observability import AgentTrace
from .planner import Planner
from .repair import RepairEngine
from .state import AgentState
from .verifier import AgentVerifier


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
    ):
        # Default to PcbnewBackend if available, else SexprBackend fallback
        if backend is None:
            pcb_be = PcbnewBackend()
            self.backend = pcb_be if pcb_be.is_available() else SexprBackend()
        else:
            self.backend = backend

        self.planner = planner or Planner()
        self.executor = executor or Executor(self.backend)
        self.verifier = verifier or AgentVerifier()
        self.repair_engine = repair_engine or RepairEngine(max_retries=max_retries)
        self.max_retries = max_retries

        self.state = AgentState()
        self.context = AgentContext()

    def run(
        self,
        user_request: str,
        domain: str = "pcb",
        on_step: Optional[Callable[[str, Any], None]] = None,
        auto_save: bool = False,
    ) -> Dict[str, Any]:
        """Execute a natural language user request through the agent lifecycle."""
        trace = AgentTrace(user_request=user_request)
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

                    # Step 6: ANALYZE ERROR & REPAIR
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
                self.backend.save_board()
                trace.record("BOARD_SAVED", "Board saved successfully")
        else:
            transaction.rollback()
            trace.record("TRANSACTION_ROLLED_BACK", "Transaction rolled back due to verification failure")

        final_state = self.backend.get_state(domain)
        trace.finish(success=all_passed, final_state=final_state)

        return {
            "success": all_passed,
            "plan_id": plan.plan_id,
            "results": executed_results,
            "transaction_state": transaction.state.value,
            "final_state": final_state,
            "trace": trace.to_dict(),
        }
