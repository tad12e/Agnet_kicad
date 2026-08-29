"""LLM Provider abstraction and Anthropic / Claude client implementation."""

from __future__ import annotations

import abc
import os
from typing import Any, Callable, Dict, List, Optional


class LLMProvider(abc.ABC):
    """Abstract base class for LLM reasoning providers."""

    @abc.abstractmethod
    def generate_response(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        system_prompt: str = "",
        model: Optional[str] = None,
    ) -> Any:
        """Call LLM API and return response."""
        pass


class AnthropicProvider(LLMProvider):
    """Anthropic Claude API provider."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=self.api_key or None)
            except ImportError as e:
                raise ImportError("anthropic package required for Claude provider: pip install anthropic") from e
        return self._client

    def generate_response(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        system_prompt: str = "",
        model: Optional[str] = None,
    ) -> Any:
        client = self._get_client()
        kwargs: Dict[str, Any] = {
            "model": model or "claude-3-7-sonnet-20250219",
            "max_tokens": 1024,
            "messages": messages,
        }
        if system_prompt:
            kwargs["system"] = system_prompt
        if tools:
            kwargs["tools"] = tools

        return client.messages.create(**kwargs)
