"""Smoke test only: proves the ADK agent is wired and its tool returns facts, without
calling Gemini. Routing quality is measured by tests/eval/run_golden.py in M8."""

import importlib

import pytest

import teduh_agent.agent as agent_module
from teduh_agent.agent import count_kelurahan, root_agent


class FakeToolContext:
    def __init__(self) -> None:
        self.state: dict = {}


@pytest.mark.unit
def test_root_agent_is_named_teduh_coordinator():
    # tests/eval/golden_questions.yaml matches on agent names, so this is a contract.
    assert root_agent.name == "teduh_coordinator"


@pytest.mark.unit
def test_root_agent_model_comes_from_the_environment(monkeypatch):
    monkeypatch.setenv("TEDUH_MODEL", "gemini-test-model")
    try:
        reloaded = importlib.reload(agent_module)
        assert reloaded.MODEL == "gemini-test-model"
    finally:
        monkeypatch.delenv("TEDUH_MODEL", raising=False)
        importlib.reload(agent_module)


@pytest.mark.integration
def test_count_kelurahan_returns_a_fact_with_a_data_source():
    # Arrange
    ctx = FakeToolContext()

    # Act
    result = count_kelurahan(ctx)

    # Assert
    assert result["facts"], "tool wajib mengembalikan facts (CLAUDE.md aturan 2)"
    only = result["facts"][0]
    assert only["source"] == "data:grid_features@v1"
    assert only["value"] == 264
    assert only["unit"] == "kelurahan"


@pytest.mark.integration
def test_count_kelurahan_records_its_fact_in_the_session_ledger():
    # Arrange
    ctx = FakeToolContext()

    # Act
    count_kelurahan(ctx)

    # Assert
    assert ctx.state["facts"][0]["id"] == "data.kelurahan_count"
