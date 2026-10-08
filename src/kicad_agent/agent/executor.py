"""Deterministic Action Executor."""

from __future__ import annotations

from typing import Dict, Optional

from ..backends.base import KiCadBackend
from ..core.actions import Action
from ..core.plans import Plan
from ..core.results import ActionResult
from ..core.transactions import Transaction
from ..core.validator import ActionValidator


class Executor:
    """Dispatches validated actions to the active KiCad backend."""

    def __init__(self, backend: KiCadBackend):
        self.backend = backend

    def execute_action(self, action: Action, transaction: Optional[Transaction] = None) -> ActionResult:
        """Execute a single Action IR object via the backend."""
        validation_errors = ActionValidator.validate_action(
            action, current_state=self.backend.get_state(action.domain.value)
        )
        if validation_errors:
            return ActionResult(
                action_id=action.action_id,
                success=False,
                error=validation_errors[0],
                data={"diagnostics": [error.to_dict() for error in validation_errors]},
                backend_used=self.backend.name,
            )
        if transaction:
            transaction.stage(action)

        result = self.backend.execute(action)

        if transaction:
            transaction.record_result(result)

        return result

    def execute_plan(self, plan: Plan, transaction: Optional[Transaction] = None) -> Dict[str, ActionResult]:
        """Execute all actions in a plan in dependency order."""
        results: Dict[str, ActionResult] = {}

        for action in plan.actions:
            res = self.execute_action(action, transaction=transaction)
            results[action.action_id] = res
            if not res.success:
                break

        return results
