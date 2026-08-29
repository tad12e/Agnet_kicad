"""Transaction and checkpoint representation for staged execution and rollback."""

from __future__ import annotations

import enum
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .actions import Action
from .results import ActionResult


class TransactionState(str, enum.Enum):
    """Lifecycle state of a transaction."""
    PENDING = "pending"
    ACTIVE = "active"
    COMMITTED = "committed"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"


@dataclass
class Transaction:
    """Represents a transaction context for staging actions and supporting rollback.
    
    Attributes:
        transaction_id: Unique identifier for transaction.
        state: Current lifecycle state.
        staged_actions: Actions queued or executed under this transaction.
        results: Action execution results.
        checkpoint_data: Saved snapshot data for rollback (e.g. backup file path or state).
        created_at: Unix timestamp.
    """
    transaction_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    state: TransactionState = TransactionState.PENDING
    staged_actions: List[Action] = field(default_factory=list)
    results: List[ActionResult] = field(default_factory=list)
    checkpoint_data: Optional[Dict[str, Any]] = None
    created_at: float = field(default_factory=time.time)

    def stage(self, action: Action) -> None:
        """Stage an action within the transaction."""
        self.staged_actions.append(action)

    def record_result(self, result: ActionResult) -> None:
        """Record the outcome of an action."""
        self.results.append(result)
        if not result.success:
            self.state = TransactionState.FAILED

    def commit(self) -> None:
        """Mark transaction as successfully committed."""
        self.state = TransactionState.COMMITTED

    def rollback(self) -> None:
        """Mark transaction as rolled back."""
        self.state = TransactionState.ROLLED_BACK
