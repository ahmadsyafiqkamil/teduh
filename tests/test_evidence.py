"""The evidence base is what keeps a model number honest. The metric-comparability test is
the important one: interventions.json records roof SURFACE temperature drops of up to 13 C,
and presenting that next to an area-average LST change of -0.8 C would be badly misleading
even though both are real published figures."""

import pytest

from teduh_agent.tools.evidence import COMPARABLE_METRIC, evidence_for, get_evidence


class FakeToolContext:
    def __init__(self) -> None:
        self.state: dict = {}


@pytest.mark.integration
def test_returns_evidence_for_each_simulated_intervention():
    for intervention in ("tree_planting", "cool_roof", "green_roof"):
        result = evidence_for(intervention)
        assert result["evidence"], f"tidak ada bukti untuk {intervention}"


@pytest.mark.integration
def test_every_entry_is_citable():
    for entry in evidence_for("tree_planting")["evidence"]:
        assert entry["source_title"]
        assert entry["url_or_doi"]
        assert entry["year"]


@pytest.mark.integration
def test_entries_declare_whether_their_metric_is_comparable_to_model_output():
    # A roof-surface temperature drop is not an area cooling. The flag makes the agent
    # able to say so instead of putting the two side by side as equals.
    for entry in evidence_for("cool_roof")["evidence"]:
        assert "comparable_to_model" in entry
        assert entry["comparable_to_model"] == (entry["metric"] == COMPARABLE_METRIC)


@pytest.mark.integration
def test_comparable_entries_are_listed_first():
    entries = evidence_for("cool_roof")["evidence"]
    flags = [entry["comparable_to_model"] for entry in entries]
    assert flags == sorted(flags, reverse=True)


@pytest.mark.integration
def test_tree_planting_surfaces_the_kuala_lumpur_ndvi_range():
    # CONCEPT §7.5 names this as the comparison to show: -1.4 to 0.1 degC for +25% NDVI.
    entries = evidence_for("tree_planting")["evidence"]
    kl = next(e for e in entries if e["id"] == "ev_ndvi_kl_2025")
    assert kl["value_min"] == pytest.approx(-1.4)
    assert kl["value_max"] == pytest.approx(0.1)
    assert kl["comparable_to_model"] is True


@pytest.mark.integration
def test_facts_cite_the_evidence_id_as_their_source():
    for entry in evidence_for("tree_planting")["facts"]:
        assert entry["source"].startswith("evidence:")


@pytest.mark.integration
def test_facts_record_both_bounds_of_a_range():
    ids = {f["id"] for f in evidence_for("tree_planting")["facts"]}
    assert "evidence.ev_ndvi_kl_2025.min" in ids
    assert "evidence.ev_ndvi_kl_2025.max" in ids


@pytest.mark.integration
def test_unknown_intervention_says_so_without_inventing_evidence():
    result = evidence_for("teleportasi")
    assert result["evidence"] == []
    assert "error" in result
    assert result["facts"] == []


@pytest.mark.integration
def test_get_evidence_records_into_the_session_ledger():
    ctx = FakeToolContext()
    get_evidence("cool_roof", ctx)
    assert ctx.state["facts"]


@pytest.mark.integration
def test_get_evidence_does_not_record_for_an_unknown_intervention():
    ctx = FakeToolContext()
    get_evidence("teleportasi", ctx)
    assert ctx.state.get("facts", []) == []
