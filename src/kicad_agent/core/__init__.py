"""Core domain-neutral definitions and Intermediate Representations (IR).

Contains Action, Plan, Goal, Error, Transaction, and Result abstractions
shared across both PCB and Schematic subsystems.
"""

from .actions import Action, ActionDomain, ActionType
from .errors import AgentError, ErrorCategory, ErrorSeverity
from .goals import Goal, GoalType
from .plans import Plan
from .results import ActionResult, VerificationResult
from .transactions import Transaction, TransactionState

__all__ = [
    "Action",
    "ActionDomain",
    "ActionType",
    "ActionResult",
    "AgentError",
    "ErrorCategory",
    "ErrorSeverity",
    "Goal",
    "GoalType",
    "Plan",
    "Transaction",
    "TransactionState",
    "VerificationResult",
]
