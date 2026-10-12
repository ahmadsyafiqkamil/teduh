"""Sub-agent wiring. The tool-partition test is the one that matters: if heat_analyst can
reach optimize_portfolio, the coordinator stops routing and the golden-question
expected_agent assertions become meaningless."""

import pytest

from teduh_agent.sub_agents import build_all


@pytest.fixture(scope="module")
def agents() -> dict:
    return {agent.name: agent for agent in build_all()}


def _tool_names(agent) -> set[str]:
    return {getattr(tool, "__name__", getattr(tool, "name", str(tool))) for tool in agent.tools}


@pytest.mark.unit
def test_the_four_sub_agents_are_named_as_the_eval_set_expects(agents):
    assert "heat_analyst" in agents
    assert "intervention_planner" in agents
    # policy_writer and roof_inspector need M5/M6 tools; skip cleanly until then.
    for optional in ("policy_writer", "roof_inspector"):
        if optional not in agents:
            pytest.skip(f"{optional} belum aktif: tool M5/M6 belum ada")


@pytest.mark.unit
def test_heat_analyst_has_exactly_its_four_tools(agents):
    assert _tool_names(agents["heat_analyst"]) == {
        "find_area",
        "get_area_profile",
        "rank_priority_areas",
        "explain_drivers",
    }


@pytest.mark.unit
def test_intervention_planner_has_exactly_its_three_tools(agents):
    assert _tool_names(agents["intervention_planner"]) == {
        "simulate_intervention",
        "optimize_portfolio",
        "get_evidence",
    }


@pytest.mark.unit
def test_no_sub_agent_can_reach_another_sub_agents_tools(agents):
    # Overlapping tools make the coordinator's routing decision cosmetic.
    seen: dict[str, str] = {}
    for name, agent in agents.items():
        for tool in _tool_names(agent):
            assert tool not in seen, f"{tool} dimiliki {seen.get(tool)} dan {name}"
            seen[tool] = name


@pytest.mark.unit
def test_every_sub_agent_carries_the_shared_rules(agents):
    for name, agent in agents.items():
        assert "tidak berasal dari" in agent.instruction.lower(), (
            f"{name} kehilangan aturan provenance"
        )


@pytest.mark.unit
def test_every_sub_agent_has_a_description_the_coordinator_can_route_on(agents):
    for name, agent in agents.items():
        assert agent.description, f"{name} tanpa description"
        assert len(agent.description) > 20, f"description {name} terlalu pendek untuk routing"


@pytest.mark.unit
def test_every_sub_agent_uses_the_model_from_the_environment(monkeypatch):
    from teduh_agent.llm import model_name

    monkeypatch.delenv("TEDUH_LLM_BACKEND", raising=False)
    monkeypatch.setenv("TEDUH_MODEL", "gemini-test-model")

    for agent in build_all():
        assert agent.model == model_name()
