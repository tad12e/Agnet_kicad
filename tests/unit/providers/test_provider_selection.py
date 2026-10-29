import pytest

# Load the agent package first; the existing provider/context modules share
# the package-level import graph.
from kicad_agent.agent.agent import KiCadAgent  # noqa: F401
from kicad_agent.providers import (
    AnthropicProvider,
    GeminiProvider,
    MockLLMProvider,
    OpenAICompatibleProvider,
    create_configured_provider,
)
from kicad_agent.providers.factory import configured_provider


def test_runtime_provider_defaults_to_anthropic(monkeypatch):
    monkeypatch.delenv("KICAD_AGENT_PROVIDER", raising=False)

    provider = create_configured_provider()

    assert isinstance(provider, AnthropicProvider)


def test_gemini_provider_can_be_selected(monkeypatch):
    monkeypatch.setenv("KICAD_AGENT_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-123")

    provider = create_configured_provider()

    assert isinstance(provider, GeminiProvider)
    assert provider.api_key == "test-key-123"
    assert "generativelanguage.googleapis.com" in provider.base_url


def test_gemini_auto_detected_from_api_key(monkeypatch):
    monkeypatch.delenv("KICAD_AGENT_PROVIDER", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")

    provider = configured_provider()

    assert isinstance(provider, GeminiProvider)
    assert provider.api_key == "test-gemini-key"


def test_mock_provider_requires_explicit_opt_in(monkeypatch):
    monkeypatch.setenv("KICAD_AGENT_PROVIDER", "mock")

    provider = create_configured_provider()

    assert isinstance(provider, MockLLMProvider)


def test_openai_compatible_provider_can_be_selected(monkeypatch):
    monkeypatch.setenv("KICAD_AGENT_PROVIDER", "openai-compatible")
    monkeypatch.setenv("KICAD_AGENT_OPENAI_BASE_URL", "http://localhost:1234/v1")
    monkeypatch.setenv("KICAD_AGENT_MODEL", "local-model")

    provider = create_configured_provider()

    assert isinstance(provider, OpenAICompatibleProvider)
    assert provider.base_url == "http://localhost:1234/v1"
    assert provider.model == "local-model"


def test_unknown_provider_is_rejected(monkeypatch):
    monkeypatch.setenv("KICAD_AGENT_PROVIDER", "unknown")

    with pytest.raises(ValueError, match="Unknown KICAD_AGENT_PROVIDER"):
        create_configured_provider()
