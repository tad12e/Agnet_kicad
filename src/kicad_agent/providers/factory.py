"""Consistent provider resolution for all agent entry points."""

from __future__ import annotations

import os
from typing import Optional

from .llm import AnthropicProvider, LLMProvider


def configured_provider(
    provider: Optional[LLMProvider] = None,
) -> Optional[LLMProvider]:
    """Return an explicit provider or the configured production provider."""
    if provider is not None:
        return provider
    provider_name = os.environ.get("KICAD_AGENT_PROVIDER", "anthropic").lower()
    if provider_name != "anthropic":
        raise ValueError(
            f"Unsupported KICAD_AGENT_PROVIDER '{provider_name}'. "
            "Supported providers: anthropic."
        )
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    return AnthropicProvider()
