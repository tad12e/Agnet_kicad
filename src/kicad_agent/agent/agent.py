"""Top-level KiCad AI Agent Orchestrator.

Manages the complete lifecycle:
observe -> plan -> validate -> execute -> verify -> repair -> retry -> finalize
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from ..backends.base import KiCadBackend
from ..backends.pcbnew import PcbnewBackend
from ..backends.sexpr import SexprBackend
from ..core.actions import Action
from ..core.errors import AgentError, ErrorCategory
from ..core.plans import Plan
from ..core.results import ActionResult, VerificationResult
from ..core.transactions import Transaction
from .context import AgentContext
from .error_analyzer import ErrorAnalyzer
from .executor import Executor
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
        self.repair_engine = repair_engine or RepairEngine()

        self.state = AgentState()
        self.context = AgentContext()

    def run(
        self,
        user_request: str,
        domain: str = "pcb",
        on_step: Optional[Callable[[str, Any], None]] = None,
    ) -> Dict[str, Any]:
        """Execute a natural language user request through the agent lifecycle."""
        self.state.active_domain = domain
        self.state.iteration_count = 0

        if on_step:
            on_step("planning", {"request": user_request})

        # 1. Plan
        plan = self.planner.plan_request(user_request, domain=domain)
        self.state.current_plan = plan

        executed_results = []
        all_passed = True

        transaction = Transaction()

        for action in plan.actions:
            self.state.iteration_count += 1
            if self.state.iteration_count > self.state.max_iterations:
                break

            if on_step:
                on_step("executing_action", action.to_dict())

            # 2. Execute
            result = self.executor.execute_action(action, transaction=transaction)
            self.state.executed_actions.append(action)
            self.state.action_results.append(result)

            # 3. Verify
            verification = self.verifier.verify_action(action, result)
            self.state.verification_history.append(verification)

            if on_step:
                on_step("verified_action", verification.to_dict())

            # 4. Repair if failed
            if not verification.passed or not result.success:
                all_passed = False
                repaired_action = self.repair_engine.attempt_repair(action, result, verification)

                if repaired_action:
                    if on_step:
                        on_step("attempting_repair", repaired_action.to_dict())

                    repaired_result = self.executor.execute_action(repaired_action, transaction=transaction)
                    repaired_verification = self.verifier.verify_action(repaired_action, repaired_result)

                    executed_results.append({
                        "action": repaired_action.to_dict(),
                        "result": repaired_result.to_dict(),
                        "verification": repaired_verification.to_dict(),
                        "repaired": True,
                    })

                    if repaired_verification.passed and repaired_result.success:
                        all_passed = True
                else:
                    executed_results.append({
                        "action": action.to_dict(),
                        "result": result.to_dict(),
                        "verification": verification.to_dict(),
                    })
            else:
                executed_results.append({
                    "action": action.to_dict(),
                    "result": result.to_dict(),
                    "verification": verification.to_dict(),
                })

        if all_passed:
            transaction.commit()
        else:
            transaction.rollback()

        return {
            "success": all_passed,
            "plan_id": plan.plan_id,
            "results": executed_results,
            "transaction_state": transaction.state.value,
        }
