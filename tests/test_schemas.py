"""Validation at the trust boundary. Anything that reaches a tool from HTTP has already
passed through here, which is why the tools themselves can assume well-formed types."""

import pytest
from pydantic import ValidationError

from api.schemas import InterventionInput, OptimizeRequest, SimulateRequest, fail, ok


@pytest.mark.unit
def test_envelope_marks_success_and_carries_data():
    assert ok({"a": 1}) == {"success": True, "data": {"a": 1}, "error": None}


@pytest.mark.unit
def test_envelope_marks_failure_and_carries_a_message():
    assert fail("tidak ada") == {"success": False, "data": None, "error": "tidak ada"}


@pytest.mark.unit
def test_intervention_accepts_a_known_type_and_level():
    assert InterventionInput(type="cool_roof", level="medium").level == "medium"


@pytest.mark.unit
def test_intervention_rejects_an_unknown_type():
    with pytest.raises(ValidationError):
        InterventionInput(type="cool_pavement", level="low")


@pytest.mark.unit
def test_intervention_rejects_an_unknown_level():
    with pytest.raises(ValidationError):
        InterventionInput(type="cool_roof", level="ekstrem")


@pytest.mark.unit
def test_intervention_requires_either_a_level_or_params():
    with pytest.raises(ValidationError, match="level"):
        InterventionInput(type="cool_roof")


@pytest.mark.unit
def test_intervention_accepts_explicit_params_without_a_level():
    item = InterventionInput(type="tree_planting", params={"canopy_increase_pp": 7.5})
    assert item.params == {"canopy_increase_pp": 7.5}


@pytest.mark.unit
def test_simulate_rejects_a_malformed_kel_id():
    with pytest.raises(ValidationError):
        SimulateRequest(
            kel_ids=["bukan-id"], interventions=[InterventionInput(type="cool_roof",
                                                                   level="low")]
        )


@pytest.mark.unit
def test_simulate_accepts_a_real_kel_id():
    request = SimulateRequest(
        kel_ids=["ID3173040002"],
        interventions=[InterventionInput(type="cool_roof", level="low")],
    )
    assert request.kel_ids == ["ID3173040002"]


@pytest.mark.unit
def test_simulate_rejects_an_empty_intervention_list():
    with pytest.raises(ValidationError):
        SimulateRequest(kel_ids=["ID3173040002"], interventions=[])


@pytest.mark.unit
def test_simulate_caps_the_number_of_kelurahan():
    # Each kelurahan is a model prediction over its cells; an unbounded list is a trivial
    # way to make one request occupy the whole instance.
    with pytest.raises(ValidationError):
        SimulateRequest(
            kel_ids=[f"ID31730400{i:02d}" for i in range(30)],
            interventions=[InterventionInput(type="cool_roof", level="low")],
        )


@pytest.mark.unit
def test_optimize_rejects_a_non_positive_budget():
    with pytest.raises(ValidationError):
        OptimizeRequest(budget_idr=0)


@pytest.mark.unit
def test_optimize_rejects_an_absurd_budget():
    with pytest.raises(ValidationError):
        OptimizeRequest(budget_idr=10**15)


@pytest.mark.unit
def test_optimize_rejects_an_equity_share_above_one():
    with pytest.raises(ValidationError):
        OptimizeRequest(budget_idr=1_000_000, equity_share=1.5)


@pytest.mark.unit
def test_optimize_defaults_scope_to_all_and_equity_to_none():
    request = OptimizeRequest(budget_idr=2_000_000_000)
    assert request.scope == "all"
    assert request.equity_share is None
