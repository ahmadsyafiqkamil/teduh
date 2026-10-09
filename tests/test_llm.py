"""Model resolution: Gemini default string, plus the [OI]-compatible escape hatch."""

import pytest

from teduh_agent.llm import resolve_model


@pytest.mark.unit
def test_default_backend_returns_the_model_id_as_a_string(monkeypatch):
    monkeypatch.delenv("TEDUH_LLM_BACKEND", raising=False)
    monkeypatch.setenv("TEDUH_MODEL", "gemini-test-model")
    assert resolve_model() == "gemini-test-model"


@pytest.mark.unit
def test_openai_backend_returns_a_model_instance(monkeypatch):
    monkeypatch.setenv("TEDUH_LLM_BACKEND", "openai")
    monkeypatch.setenv("TEDUH_MODEL", "deepseek-v4-1-flash")
    monkeypatch.setenv("TEDUH_LLM_BASE_URL", "https://kenari.id/v1")
    monkeypatch.setenv("TEDUH_LLM_API_KEY", "kn-test")

    model = resolve_model()
    assert model.model == "deepseek-v4-1-flash"
    assert model.base_url == "https://kenari.id/v1"


@pytest.mark.unit
def test_backend_is_case_insensitive(monkeypatch):
    monkeypatch.setenv("TEDUH_LLM_BACKEND", "OPENAI")
    monkeypatch.setenv("TEDUH_MODEL", "deepseek-v4-1-flash")
    assert resolve_model().model == "deepseek-v4-1-flash"
