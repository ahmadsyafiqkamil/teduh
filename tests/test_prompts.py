"""The system instruction is the only thing standing between a helpful agent and a
confident fabricator. These tests pin the clauses CONCEPT §8.3 requires, because a prompt
edit during golden-question tuning is exactly when one of them gets dropped by accident."""

import pytest

from teduh_agent.prompts import SHARED, available, compose, load

AGENT_PROMPTS = (
    "coordinator",
    "heat_analyst",
    "intervention_planner",
    "policy_writer",
    "roof_inspector",
)


@pytest.mark.unit
def test_every_agent_prompt_exists():
    for name in AGENT_PROMPTS:
        assert load(name).strip(), f"{name}.md kosong"


@pytest.mark.unit
def test_available_lists_the_shared_rules_and_every_agent():
    names = set(available())
    assert SHARED in names
    assert set(AGENT_PROMPTS) <= names


@pytest.mark.unit
def test_load_rejects_an_unknown_prompt():
    with pytest.raises(FileNotFoundError, match="tidak ada"):
        load("tidak_ada")


@pytest.mark.unit
def test_compose_prepends_the_shared_rules():
    composed = compose("heat_analyst")
    assert composed.startswith(load(SHARED).strip())
    assert load("heat_analyst").strip() in composed


@pytest.mark.unit
def test_shared_rules_forbid_inventing_numbers():
    # CONCEPT §8.3, and the reason the whole facts architecture exists.
    text = load(SHARED).lower()
    assert "jangan" in text
    assert "angka" in text
    assert "tool" in text


@pytest.mark.unit
def test_shared_rules_require_indonesian():
    assert "bahasa indonesia" in load(SHARED).lower()


@pytest.mark.unit
def test_shared_rules_forbid_a_note_before_a_tool_call():
    # Observed in the browser: the model narrated what it was about to do ("I'll look up
    # Kelurahan Rawa Buaya first.") in the same turn as the functionCall, and that aside
    # reached the screen. The rule must tell it to go straight to the tool and write only
    # the final answer.
    text = load(SHARED).lower()
    assert "jangan menulis catatan" in text
    assert "langsung panggil tool" in text


@pytest.mark.unit
def test_shared_rules_require_the_surface_temperature_caveat():
    text = load(SHARED).lower()
    assert "permukaan" in text
    assert "indikatif" in text


@pytest.mark.unit
def test_shared_rules_tell_the_agent_to_name_the_extrapolated_feature():
    # The flag alone is misleading: the planner must be told WHICH feature left the envelope.
    text = load(SHARED).lower()
    assert "extrapolated_features" in text


@pytest.mark.unit
def test_shared_rules_require_prioritising_vulnerable_residents():
    assert "rentan" in load(SHARED).lower()


@pytest.mark.unit
def test_shared_rules_forbid_inventing_prices():
    text = load(SHARED).lower()
    assert "harga" in text


@pytest.mark.unit
def test_every_composed_prompt_carries_the_no_invented_numbers_rule():
    for name in AGENT_PROMPTS:
        assert "tidak berasal dari" in compose(name).lower(), (
            f"{name} kehilangan aturan provenance"
        )


@pytest.mark.unit
def test_intervention_planner_is_told_to_cite_literature():
    assert "get_evidence" in load("intervention_planner")


@pytest.mark.unit
def test_policy_writer_is_told_the_marker_syntax():
    text = load("policy_writer")
    assert "[[F:" in text
    assert "render_policy_brief" in text


@pytest.mark.unit
def test_roof_inspector_carries_the_asbestos_safety_rule():
    text = load("roof_inspector").lower()
    assert "asbes" in text


@pytest.mark.unit
def test_coordinator_names_every_sub_agent_it_can_route_to():
    text = load("coordinator")
    for name in ("heat_analyst", "intervention_planner", "policy_writer", "roof_inspector"):
        assert name in text
