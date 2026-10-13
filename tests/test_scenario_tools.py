"""The tool layer over model/scenario.py. Two things are checked here that the engine tests
cannot: that the agent-facing JSON shape is accepted, and that every scenario answer carries
the literature comparison CONCEPT §7.5 requires -- a model number with no published range
beside it is exactly the overclaiming this product is designed to avoid."""

import pytest

from teduh_agent.tools.scenario_tools import simulate_intervention


class FakeToolContext:
    def __init__(self) -> None:
        self.state: dict = {}


@pytest.mark.integration
def test_accepts_an_intervention_given_by_level():
    result = simulate_intervention(["ID3173040002"], [{"type": "cool_roof", "level": "medium"}])
    assert result["results"][0]["kel_id"] == "ID3173040002"
    assert result["results"][0]["kel_name"] == "Kampung Rawa"


@pytest.mark.integration
def test_accepts_an_intervention_given_by_explicit_params():
    result = simulate_intervention(
        ["ID3173040002"],
        [{"type": "tree_planting", "params": {"canopy_increase_pp": 7.5}}],
    )
    assert result["results"][0]["delta_lst_c"] <= 1e-9


@pytest.mark.integration
def test_simulates_several_kelurahan_in_one_call():
    result = simulate_intervention(
        ["ID3173040002", "ID3172030001"], [{"type": "cool_roof", "level": "low"}]
    )
    assert {row["kel_id"] for row in result["results"]} == {"ID3173040002", "ID3172030001"}


@pytest.mark.integration
def test_every_result_carries_the_indicative_caveat():
    result = simulate_intervention(["ID3173040002"], [{"type": "cool_roof", "level": "low"}])
    assert "indikatif" in result["note"].lower()
    assert "permukaan" in result["note"].lower()


@pytest.mark.integration
def test_every_result_carries_a_literature_comparison():
    # CONCEPT §7.5: the model number is always shown next to a published range.
    result = simulate_intervention(["ID3173040002"], [{"type": "cool_roof", "level": "medium"}])
    assert result["evidence"], "hasil skenario tanpa pembanding literatur"
    assert all(entry["url_or_doi"] for entry in result["evidence"])


@pytest.mark.integration
def test_emits_a_fact_for_each_reported_number():
    result = simulate_intervention(["ID3173040002"], [{"type": "cool_roof", "level": "medium"}])
    ids = {f["id"] for f in result["facts"]}
    assert "sim.ID3173040002.delta_lst" in ids
    assert "sim.ID3173040002.cost" in ids
    assert "sim.ID3173040002.area" in ids
    assert "sim.ID3173040002.vulnerable_benefiting" in ids


@pytest.mark.integration
def test_cost_facts_cite_their_price_source():
    result = simulate_intervention(["ID3173040002"], [{"type": "tree_planting",
                                                       "level": "low"}])
    cost_facts = [f for f in result["facts"] if f["id"].endswith(".cost")]
    assert cost_facts
    for entry in cost_facts:
        assert entry["source"].startswith("assumption:") or "Kepgub" in entry["source"]


@pytest.mark.integration
def test_extrapolation_is_surfaced_in_the_payload():
    result = simulate_intervention(["ID3173040002"], [{"type": "cool_roof", "level": "high"}])
    assert "extrapolation" in result["results"][0]


@pytest.mark.integration
def test_records_facts_into_the_session_ledger():
    ctx = FakeToolContext()
    simulate_intervention(["ID3173040002"], [{"type": "cool_roof", "level": "low"}], ctx)
    assert ctx.state["facts"]


@pytest.mark.integration
def test_rejects_an_unknown_kelurahan_without_guessing():
    result = simulate_intervention(["ID9999999999"], [{"type": "cool_roof", "level": "low"}])
    assert "error" in result
    assert result["facts"] == []


@pytest.mark.integration
def test_rejects_an_unknown_intervention_type():
    result = simulate_intervention(["ID3173040002"], [{"type": "cool_pavement",
                                                       "level": "low"}])
    assert "error" in result


@pytest.mark.integration
def test_rejects_an_unknown_level():
    result = simulate_intervention(["ID3173040002"], [{"type": "cool_roof",
                                                       "level": "ekstrem"}])
    assert "error" in result


@pytest.mark.integration
def test_rejects_an_empty_intervention_list():
    result = simulate_intervention(["ID3173040002"], [])
    assert "error" in result


@pytest.mark.integration
def test_says_so_plainly_when_the_model_is_missing(monkeypatch):
    import teduh_agent.tools.scenario_tools as module

    class _NoBooster:
        booster = None

        def __getattr__(self, name):
            from teduh_agent.store import load

            return getattr(load(), name)

    monkeypatch.setattr(module, "get_store", lambda: _NoBooster())
    result = simulate_intervention(["ID3173040002"], [{"type": "cool_roof", "level": "low"}])
    assert "error" in result
    assert "model" in result["error"].lower()
