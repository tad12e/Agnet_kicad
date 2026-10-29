"""Consistent provider resolution for all agent entry points."""

from __future__ import annotations

import os
from typing import Optional

from .llm import AnthropicProvider, GeminiProvider, LLMProvider


def configured_provider(
    provider: Optional[LLMProvider] = None,
) -> Optional[LLMProvider]:
    """Return an explicit provider or the configured production provider."""
    if provider is not None:
        return provider

    provider_name = os.environ.get("KICAD_AGENT_PROVIDER", "").strip().lower()

    if not provider_name:
        if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
            return GeminiProvider()
        provider_name = "anthropic"

    if provider_name in ("gemini", "google"):
        if not (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")):
            return None
        return GeminiProvider()
    elif provider_name == "anthropic":
        if not os.environ.get("ANTHROPIC_API_KEY"):
            return None
        return AnthropicProvider()
    else:
        raise ValueError(
            f"Unsupported KICAD_AGENT_PROVIDER '{provider_name}'. "
            "Supported providers: anthropic, gemini."
        )
