"""WAJIB menurut CLAUDE.md: total cost must never exceed the budget, and the equity share
constraint must hold.

This tool puts a spending plan in front of a city government. A portfolio that quietly
overruns the budget, or that drifts away from the most vulnerable kelurahan, is the single
most damaging thing TEDUH could produce."""

import pytest

from teduh_agent.tools.optimize import (
    LAMBDA_GENERAL_POP,
    TOP_QUINTILE,
    build_candidates,
    optimize_portfolio,
    solve,
)

BUDGET_2B = 2_000_000_000


class FakeToolContext:
    def __init__(self) -> None:
        self.state: dict = {}


@pytest.fixture(scope="module")
def candidates():
    return build_candidates(["ID3173040002", "ID3172030001", "ID3172070002"])


# --- candidate generation ------------------------------------------------------------

@pytest.mark.integration
def test_candidates_exclude_interventions_that_benefit_no_vulnerable_resident(candidates):
    # A package that cools no vulnerable resident to the benefit threshold (>= 0.5 °C) is
    # dropped at generation time, never offered to the solver.
    assert candidates
    assert all(c.vulnerable_benefiting > 0 for c in candidates)


@pytest.mark.integration
def test_candidates_keep_cool_roof_for_every_kelurahan(candidates):
    # Cool roof clears the benefit threshold in these dense kelurahan, so its three levels
    # survive for every area -- the filter must not over-prune a genuinely useful package.
    cool_roofs = {c.kel_id for c in candidates if c.intervention_type == "cool_roof"}
    assert cool_roofs == {"ID3173040002", "ID3172030001", "ID3172070002"}


@pytest.mark.integration
def test_candidate_value_rewards_cooling_vulnerable_residents(candidates):
    # Value is sum((pop_u5 + pop_65p + lambda*pop) * -delta_lst), so a warming candidate
    # cannot score above a cooling one.
    for candidate in candidates:
        if candidate.delta_lst_c < 0:
            assert candidate.value >= 0


@pytest.mark.integration
def test_candidates_know_whether_they_sit_in_the_top_hvi_quintile(candidates):
    # Kampung Rawa is HVI rank 1 of 264; Pondok Ranggon is rank 262.
    flags = {c.kel_id: c.in_top_quintile for c in candidates}
    assert flags["ID3173040002"] is True
    assert flags["ID3172030001"] is False


# --- the mandatory constraints -------------------------------------------------------

@pytest.mark.integration
def test_total_cost_never_exceeds_the_budget(candidates):
    # CLAUDE.md names this test.
    for budget in (50_000_000, 500_000_000, BUDGET_2B, 20_000_000_000):
        chosen, _ = solve(candidates, budget, equity_share=0.0)
        assert sum(c.cost_idr for c in chosen) <= budget


@pytest.mark.integration
def test_equity_constraint_directs_the_required_share_to_the_top_quintile(candidates):
    # Kampung Rawa's cheapest roof package is ~Rp 6 billion, so a Rp 2 billion budget has no
    # affordable top-quintile candidate and the constraint would be trivially infeasible.
    chosen, status = solve(candidates, 20_000_000_000, equity_share=0.6)
    if not chosen:
        pytest.skip(f"tidak ada solusi layak pada anggaran ini: {status}")
    total = sum(c.cost_idr for c in chosen)
    equitable = sum(c.cost_idr for c in chosen if c.in_top_quintile)
    assert equitable >= 0.6 * total - 1e-6


@pytest.mark.integration
def test_at_most_one_level_per_kelurahan_and_intervention(candidates):
    chosen, _ = solve(candidates, BUDGET_2B, equity_share=0.0)
    pairs = [(c.kel_id, c.intervention_type) for c in chosen]
    assert len(pairs) == len(set(pairs))


@pytest.mark.integration
def test_a_zero_budget_buys_nothing(candidates):
    chosen, _ = solve(candidates, 0, equity_share=0.0)
    assert chosen == []


@pytest.mark.integration
def test_a_larger_budget_is_never_worse(candidates):
    small, _ = solve(candidates, 200_000_000, equity_share=0.0)
    large, _ = solve(candidates, BUDGET_2B, equity_share=0.0)
    assert sum(c.value for c in large) >= sum(c.value for c in small) - 1e-6


# --- tool surface ---------------------------------------------------------------------

@pytest.mark.integration
def test_tool_reports_the_equity_share_it_actually_achieved():
    result = optimize_portfolio("ID3173", BUDGET_2B)
    if "error" in result:
        pytest.skip(result["error"])
    assert 0.0 <= result["equity_share_achieved"] <= 1.0


@pytest.mark.integration
def test_tool_defaults_the_equity_share_to_the_config_value():
    result = optimize_portfolio("ID3173", BUDGET_2B)
    if "error" in result:
        pytest.skip(result["error"])
    assert result["equity_share_requested"] == pytest.approx(0.6)


@pytest.mark.integration
def test_tool_reports_unspent_budget():
    budget = 20_000_000_000
    result = optimize_portfolio("ID3173", budget)
    if "error" in result:
        pytest.skip(result["error"])
    # Unspent is the budget minus the actual spend, never negative.
    assert result["unspent_idr"] == pytest.approx(budget - result["total_cost_idr"])
    assert result["unspent_idr"] >= 0
    assert {"opt.unspent"} <= {f["id"] for f in result["facts"]}


@pytest.mark.integration
def test_tool_emits_facts_for_the_budget_and_the_totals():
    result = optimize_portfolio("ID3173", BUDGET_2B)
    if "error" in result:
        pytest.skip(result["error"])
    ids = {f["id"] for f in result["facts"]}
    assert {"opt.budget", "opt.total_cost", "opt.equity_share", "opt.n_packages"} <= ids


@pytest.mark.integration
def test_tool_can_restrict_the_allowed_interventions():
    # cool_roof on Jakarta Pusat's densest kelurahan starts at ~Rp 3,9 billion, so a
    # Rp 2 billion budget would leave nothing affordable and mask the assertion.
    result = optimize_portfolio("ID3173", 20_000_000_000, allowed=["cool_roof"])
    if "error" in result:
        pytest.skip(result["error"])
    assert {p["intervention_type"] for p in result["packages"]} <= {"cool_roof"}


@pytest.mark.integration
def test_tool_rejects_a_non_positive_budget():
    result = optimize_portfolio("ID3173", 0)
    assert "error" in result
    assert result["facts"] == []


@pytest.mark.integration
def test_tool_rejects_an_equity_share_outside_zero_to_one():
    result = optimize_portfolio("ID3173", BUDGET_2B, equity_share=1.5)
    assert "error" in result


@pytest.mark.integration
def test_tool_explains_infeasibility_instead_of_raising():
    # FR5.4. An impossible equity requirement must come back as prose, not a traceback.
    result = optimize_portfolio("ID3172030001", 1_000_000, equity_share=1.0)
    assert "error" in result or result["packages"] == []


@pytest.mark.integration
def test_tool_highlights_the_selected_kelurahan():
    result = optimize_portfolio("ID3173", BUDGET_2B)
    if "error" in result:
        pytest.skip(result["error"])
    assert set(result["map_highlight"]) == {p["kel_id"] for p in result["packages"]}


@pytest.mark.integration
def test_tool_accepts_an_explicit_list_of_kelurahan():
    # An explicit list must confine the solver to those areas, same guarantee as a scope.
    result = optimize_portfolio(
        kel_ids=["ID3173040002", "ID3172030001"], budget_idr=BUDGET_2B, equity_share=0.0
    )
    if "error" in result:
        pytest.skip(result["error"])
    ids = {p["kel_id"] for p in result["packages"]}
    assert ids <= {"ID3173040002", "ID3172030001"}


@pytest.mark.integration
def test_tool_rejects_unknown_kelurahan_in_the_explicit_list():
    result = optimize_portfolio(kel_ids=["ID9999999999"], budget_idr=BUDGET_2B)
    assert "error" in result
    assert result["facts"] == []


@pytest.mark.integration
def test_tool_reports_the_number_of_areas_considered():
    result = optimize_portfolio(
        kel_ids=["ID3173040002"], budget_idr=BUDGET_2B, equity_share=0.0
    )
    if "error" in result:
        pytest.skip(result["error"])
    assert result["n_areas"] == 1


@pytest.mark.unit
def test_general_population_is_weighted_below_vulnerable_residents():
    # Equity is the point of the product: a general resident must not count as much as a
    # toddler or an elderly resident.
    assert 0 < LAMBDA_GENERAL_POP < 1


@pytest.mark.unit
def test_top_quintile_is_one_fifth():
    assert pytest.approx(0.2) == TOP_QUINTILE
