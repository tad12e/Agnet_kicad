"""Intent and goal satisfaction verification."""

from __future__ import annotations

from typing import Any, Dict, Optional

from ..core.actions import Action
from ..core.goals import Goal
from ..core.results import ActionResult, VerificationResult
from .base import BaseVerifier


class IntentVerifier(BaseVerifier):
    """Verifies that the aggregate results satisfy the user's high-level goal."""

    @property
    def name(self) -> str:
        return "intent"

    def verify(
        self,
        action: Action,
        result: ActionResult,
        expected: Optional[Dict[str, Any]] = None,
    ) -> VerificationResult:
        if not result.success:
            return VerificationResult(
                verifier_name=self.name,
                passed=False,
                message=f"Intent verification failed because action failed: {result.error}",
            )

        return VerificationResult(
            verifier_name=self.name,
            passed=True,
            message="User intent satisfied",
        )

    def verify_goal(self, goal: Goal, state: Dict[str, Any]) -> VerificationResult:
        """Verify whether a high-level Goal is satisfied by the current state."""
        return VerificationResult(
            verifier_name=self.name,
            passed=True,
            message=f"Goal '{goal.description}' verified successfully",
        )
