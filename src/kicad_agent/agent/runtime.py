"""Runtime-facing entry point for executing agent tasks.

This module deliberately contains no MCP or transport concerns. Adapters
can provide a backend and translate the returned agent result into their
own protocol envelope.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from .agent import KiCadAgent
from ..core.contracts import PermissionDecision, PermissionRequest
from ..core.permissions import PermissionPolicy
from ..providers.llm import LLMProvider, create_configured_provider


AgentFactory = Callable[..., KiCadAgent]


class AgentRuntime:
    """Small boundary between callers and the KiCad agent orchestrator."""

    def __init__(self, agent_factory: AgentFactory = KiCadAgent):
        self._agent_factory = agent_factory

    def run(
        self,
        backend: Any,
        task: str,
        domain: str = "schematic",
        llm_provider: Optional[LLMProvider] = None,
        permission_policy: Optional[PermissionPolicy] = None,
        approval_resolver: Optional[Callable[[PermissionRequest], PermissionDecision]] = None,
    ) -> Dict[str, Any]:
        """Execute one task using the supplied backend.

        Validation and protocol-specific error envelopes belong to the
        caller; the runtime returns the orchestrator's result unchanged.
        """
        kwargs: Dict[str, Any] = {"backend": backend}
        if self._agent_factory is KiCadAgent:
            kwargs["llm_provider"] = llm_provider or create_configured_provider()
        elif llm_provider is not None:
            kwargs["llm_provider"] = llm_provider
        if permission_policy is not None:
            kwargs["permission_policy"] = permission_policy
        if approval_resolver is not None:
            kwargs["approval_resolver"] = approval_resolver
        agent = self._agent_factory(**kwargs)
        return agent.run(task, domain=domain)
