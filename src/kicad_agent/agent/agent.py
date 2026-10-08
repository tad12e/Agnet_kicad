"""Top-level KiCad AI Agent Orchestrator.

Provides the unified public entry point delegating to the iterative AgentController.
"""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, List, Optional

from ..backends.base import KiCadBackend
from ..backends.ipc import IPCBackend
from ..backends.pcbnew import PcbnewBackend
from ..backends.sexpr import SexprBackend
from ..core.actions import Action, ActionType
from ..core.contracts import AgentMode, PermissionDecision, PermissionRequest
from ..core.permissions import PermissionPolicy
from ..core.errors import AgentError, ErrorCategory
from ..core.plans import Plan
from ..core.results import ActionResult, VerificationResult
from ..core.transactions import Transaction
from ..core.validator import ActionValidator
from ..providers.llm import AnthropicProvider, LLMProvider, MockLLMProvider
from ..tasks import Task, TaskType, TaskValidator
from .context import AgentContext
from .controller import AgentController
from .decisions import AgentDecision, DecisionType
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
        llm_provider: Optional[LLMProvider] = None,
        planner: Optional[Planner] = None,
        executor: Optional[Executor] = None,
        verifier: Optional[AgentVerifier] = None,
        repair_engine: Optional[RepairEngine] = None,
        max_iterations: int = 20,
        max_retries: int = 3,
        fallback: Optional[KiCadBackend] = None,
        permission_policy: Optional[PermissionPolicy] = None,
        approval_resolver: Optional[Callable[[PermissionRequest], PermissionDecision]] = None,
    ):
        if backend is None:
            pcb_be = PcbnewBackend()
            self.backend = pcb_be if pcb_be.is_available() else SexprBackend()
        else:
            self.backend = backend
        if (
            fallback is not None
            and isinstance(self.backend, IPCBackend)
            and self.backend.fallback is None
        ):
            self.backend.fallback = fallback

        self.llm_provider = llm_provider or MockLLMProvider()
        self.planner = planner or Planner(provider=self.llm_provider)
        self.executor = executor or Executor(self.backend)
        self.verifier = verifier or AgentVerifier()
        self.repair_engine = repair_engine or RepairEngine(max_retries=max_retries)
        self.max_iterations = max_iterations
        self.max_retries = max_retries
        self.task_validator = TaskValidator()

        self.controller = AgentController(
            backend=self.backend,
            llm_provider=self.llm_provider,
            planner=self.planner,
            executor=self.executor,
            verifier=self.verifier,
            repair_engine=self.repair_engine,
            max_iterations=self.max_iterations,
            max_retries=self.max_retries,
            permission_policy=permission_policy,
            approval_resolver=approval_resolver,
        )

        self.state = AgentState()
        self.context = AgentContext()

    def classify_task(self, user_request: str, domain: str = "pcb") -> Task:
        """Convert a natural language request into a higher-level task object."""
        return self.controller._classify_task(user_request, domain=domain)

    def run(
        self,
        user_request: str,
        domain: str = "pcb",
        on_step: Optional[Callable[[str, Any], None]] = None,
        auto_save: bool = False,
        mode: AgentMode | str = AgentMode.BUILD,
    ) -> Dict[str, Any]:
        """Execute a natural language user request through the iterative agent loop."""
        res = self.controller.run(
            user_request=user_request,
            domain=domain,
            on_step=on_step,
            auto_save=auto_save,
            mode=mode,
        )
        self.state = self.controller.backend.get_state(domain)  # type: ignore[assignment]
        return res
