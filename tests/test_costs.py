"""Money a city might actually spend. Every figure must trace to config/costs.yaml, and the
sourced Kepgub prices must stay distinguishable from the ASUMSI ones -- that distinction is
what docs/DECISIONS.md commits to and what pipeline/verify_costs.py polices upstream."""

import pytest

from model.costs import CELL_AREA_M2, COST_KEYS, intervention_cost, trees_for_area
from model.scenario import COOL_ROOF, GREEN_ROOF, INTERVENTION_TYPES, TREE


@pytest.fixture
def costs(fixture_store):
    return fixture_store.costs_cfg


@pytest.mark.unit
def test_cell_area_matches_the_pipeline_cell_size():
    # pipeline/build_grid.py reports the WorldPop cell as 92.8 x 92.2 m at Jakarta's
    # latitude, and pipeline/aggregate_kelurahan.py uses the same product for area_km2.
    assert CELL_AREA_M2 == pytest.approx(8_556.16)


@pytest.mark.unit
def test_cost_keys_cover_exactly_the_scenario_intervention_types():
    # Guards the deliberate string duplication that avoids a circular import.
    assert set(COST_KEYS) == set(INTERVENTION_TYPES)


@pytest.mark.integration
def test_trees_for_area_uses_the_canopy_bridge_assumption(costs):
    # canopy_m2_per_tree is 12.0, kept as a SEPARATE assumption from the sourced per-tree
    # price precisely so it stays obvious which half is official.
    assert trees_for_area(120.0, costs) == pytest.approx(10.0)


@pytest.mark.integration
def test_tree_cost_combines_the_sapling_and_the_planting_operation(costs):
    # 2_702_703 (Tabebuya, Kepgub item 696.19) + 1_950_000 (rootball handling, item 660.91).
    amount, _ = intervention_cost(TREE, 12.0, costs)
    assert amount == pytest.approx(4_652_703.0)


@pytest.mark.integration
def test_tree_cost_cites_all_three_config_entries_it_used(costs):
    _, sources = intervention_cost(TREE, 12.0, costs)
    assert len(sources) == 3
    assert any("Kepgub" in source for source in sources)
    assert "ASUMSI" in sources, "canopy_m2_per_tree adalah ASUMSI dan harus terlihat"


@pytest.mark.integration
def test_cool_roof_cost_is_per_square_metre(costs):
    amount, sources = intervention_cost(COOL_ROOF, 100.0, costs)
    assert amount == pytest.approx(9_500_000.0)
    assert sources == ["ASUMSI"]


@pytest.mark.integration
def test_green_roof_cost_is_per_square_metre(costs):
    amount, sources = intervention_cost(GREEN_ROOF, 100.0, costs)
    assert amount == pytest.approx(60_000_000.0)
    assert sources == ["ASUMSI"]


@pytest.mark.integration
def test_zero_area_costs_nothing(costs):
    for itype in INTERVENTION_TYPES:
        amount, _ = intervention_cost(itype, 0.0, costs)
        assert amount == 0.0


@pytest.mark.integration
def test_cost_scales_linearly_with_area(costs):
    small, _ = intervention_cost(COOL_ROOF, 100.0, costs)
    large, _ = intervention_cost(COOL_ROOF, 1_000.0, costs)
    assert large == pytest.approx(small * 10)


@pytest.mark.integration
def test_negative_area_is_rejected(costs):
    with pytest.raises(ValueError, match="negatif"):
        intervention_cost(COOL_ROOF, -1.0, costs)


@pytest.mark.integration
def test_unknown_intervention_is_rejected(costs):
    with pytest.raises(ValueError, match="cool_pavement"):
        intervention_cost("cool_pavement", 100.0, costs)


@pytest.mark.unit
def test_a_config_entry_without_a_source_blocks_the_cost():
    # CLAUDE.md rule 4 enforced end to end: an unattributed price never becomes a number.
    broken = {"cool_roof": {"cost_idr_per_m2": {"value": 95_000}}}
    with pytest.raises(KeyError, match="source"):
        intervention_cost(COOL_ROOF, 100.0, broken)
