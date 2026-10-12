"""Root agent wiring, including the fallback CONCEPT §12 makes a day-6 decision point.

No Gemini call happens here. Routing quality is measured by tests/eval/run_golden.py in M8."""

import importlib

import pytest

import teduh_agent.agent as agent_module


def _reload(monkeypatch, **env) -> object:
    for key, value in env.items():
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)
    return importlib.reload(agent_module)


@pytest.mark.unit
def test_root_agent_is_named_teduh_coordinator():
    # tests/eval/golden_questions.yaml matches on agent names, so this is a contract.
    assert agent_module.root_agent.name == "teduh_coordinator"


@pytest.mark.unit
def test_root_agent_model_comes_from_the_environment(monkeypatch):
    reloaded = _reload(monkeypatch, TEDUH_MODEL="gemini-test-model", TEDUH_LLM_BACKEND=None)
    try:
        assert reloaded.root_agent.model == "gemini-test-model"
    finally:
        _reload(monkeypatch, TEDUH_MODEL=None)


@pytest.mark.unit
def test_multi_agent_mode_attaches_sub_agents_and_no_tools(monkeypatch):
    reloaded = _reload(monkeypatch, TEDUH_SINGLE_AGENT="0")
    try:
        root = reloaded.root_agent
        assert len(root.sub_agents) >= 2
        assert not root.tools, "koordinator tidak boleh memegang tool analisis sendiri"
    finally:
        _reload(monkeypatch, TEDUH_SINGLE_AGENT=None)


@pytest.mark.unit
def test_single_agent_mode_attaches_every_tool_and_no_sub_agents(monkeypatch):
    # CONCEPT §12: the escape hatch if multi-agent routing proves unstable.
    reloaded = _reload(monkeypatch, TEDUH_SINGLE_AGENT="1")
    try:
        root = reloaded.root_agent
        assert not root.sub_agents
        assert len(root.tools) >= 7
    finally:
        _reload(monkeypatch, TEDUH_SINGLE_AGENT=None)


@pytest.mark.unit
def test_single_agent_mode_keeps_the_same_name(monkeypatch):
    reloaded = _reload(monkeypatch, TEDUH_SINGLE_AGENT="1")
    try:
        assert reloaded.root_agent.name == "teduh_coordinator"
    finally:
        _reload(monkeypatch, TEDUH_SINGLE_AGENT=None)


@pytest.mark.unit
def test_root_instruction_carries_the_provenance_rule():
    assert "tidak berasal dari" in agent_module.root_agent.instruction.lower()


@pytest.mark.unit
def test_the_m0_example_tool_is_gone():
    assert not hasattr(agent_module, "count_kelurahan"), (
        "tool contoh M0 harus dihapus setelah tool nyata ada"
    )
