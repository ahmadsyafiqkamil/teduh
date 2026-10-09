"""WAJIB menurut CLAUDE.md: adding trees or albedo must never raise LST, and extrapolation
must be flagged.

The sign tests are the product's core safety property. If they fail, TEDUH is recommending
the opposite of the right thing to a city government, which is worse than recommending
nothing at all."""

import numpy as np
import pandas as pd
import pytest

from model.scenario import (
    COOL_ROOF,
    GREEN_ROOF,
    INTERVENTION_TYPES,
    LEVELS,
    TREE,
    Intervention,
    apply_interventions,
    from_level,
    intervened_area_m2,
    plantable_headroom,
    simulate,
    training_quantiles,
    treated_fractions,
)
from model.train import FEATURES, fit_final, prepare


@pytest.fixture(scope="module")
def trained(fixture_store):
    frame = prepare(fixture_store.grid)
    return fit_final(frame), frame


@pytest.fixture
def cells(fixture_store):
    """One kelurahan's cells: Kampung Rawa, the bare dense one."""
    grid = fixture_store.grid
    return grid[grid["kel_id"] == "ID3173040002"].copy()


@pytest.fixture
def cfg(fixture_store):
    return fixture_store.scenario_cfg


@pytest.fixture
def costs(fixture_store):
    return fixture_store.costs_cfg


def _one_cell(**overrides) -> pd.DataFrame:
    """A single synthetic cell, so a test can vary exactly one physical property."""
    row = {
        "built_frac": 0.5,
        "water_frac": 0.0,
        "tree_frac": 0.0,
        "roof_frac": 0.4,
        "ndvi": 0.2,
        "albedo": 0.13,
    }
    row.update(overrides)
    return pd.DataFrame([row])


# --- intervention construction -------------------------------------------------------

@pytest.mark.unit
def test_every_intervention_type_has_three_levels():
    for itype in INTERVENTION_TYPES:
        assert set(LEVELS[itype]) == {"low", "medium", "high"}


@pytest.mark.unit
def test_levels_increase_monotonically():
    for itype in INTERVENTION_TYPES:
        low, medium, high = (LEVELS[itype][key] for key in ("low", "medium", "high"))
        assert low < medium < high


@pytest.mark.unit
def test_from_level_builds_the_right_parameter_name():
    assert from_level(TREE, "medium").params == {"canopy_increase_pp": LEVELS[TREE]["medium"]}
    assert from_level(COOL_ROOF, "high").params == {"adoption_rate": LEVELS[COOL_ROOF]["high"]}


@pytest.mark.unit
def test_from_level_rejects_an_unknown_type():
    with pytest.raises(ValueError, match="intervensi"):
        from_level("cool_pavement", "low")


@pytest.mark.unit
def test_from_level_rejects_an_unknown_level():
    with pytest.raises(ValueError, match="level"):
        from_level(TREE, "ekstrem")


# --- physical caps -------------------------------------------------------------------

@pytest.mark.unit
def test_plantable_headroom_is_zero_on_a_fully_built_cell():
    assert plantable_headroom(_one_cell(built_frac=1.0)).iloc[0] == 0.0


@pytest.mark.unit
def test_plantable_headroom_is_zero_on_open_water():
    assert plantable_headroom(_one_cell(built_frac=0.0, water_frac=1.0)).iloc[0] == 0.0


@pytest.mark.unit
def test_plantable_headroom_excludes_canopy_that_already_exists():
    cell = _one_cell(built_frac=0.3, water_frac=0.1, tree_frac=0.4)
    assert plantable_headroom(cell).iloc[0] == pytest.approx(0.2)


@pytest.mark.integration
def test_canopy_gain_is_capped_by_available_land(cfg):
    # Asking for 20 pp of new canopy on a cell with 5 pp of bare ground must plant 5 pp.
    cell = _one_cell(built_frac=0.95, roof_frac=0.9)
    fractions = treated_fractions(cell, [Intervention(TREE, {"canopy_increase_pp": 20.0})], cfg)
    assert fractions[TREE].iloc[0] == pytest.approx(0.05)


@pytest.mark.integration
def test_cool_roof_only_treats_roof_that_exists(cfg):
    fractions = treated_fractions(
        _one_cell(), [Intervention(COOL_ROOF, {"adoption_rate": 0.5})], cfg
    )
    assert fractions[COOL_ROOF].iloc[0] == pytest.approx(0.2)


@pytest.mark.integration
def test_green_roof_only_treats_the_flat_share_of_the_roof(cfg):
    # flat_roof_share is 0.2, so half adoption on a 0.4 roof gives 0.4 * 0.2 * 0.5 = 0.04.
    fractions = treated_fractions(
        _one_cell(), [Intervention(GREEN_ROOF, {"adoption_rate": 0.5})], cfg
    )
    assert fractions[GREEN_ROOF].iloc[0] == pytest.approx(0.04)


@pytest.mark.integration
def test_cool_roof_and_green_roof_do_not_double_count_the_same_roof(cfg):
    # Both at full adoption must not treat more roof than the cell actually has.
    fractions = treated_fractions(
        _one_cell(roof_frac=0.5, built_frac=0.6),
        [
            Intervention(COOL_ROOF, {"adoption_rate": 1.0}),
            Intervention(GREEN_ROOF, {"adoption_rate": 1.0}),
        ],
        cfg,
    )
    treated_roof = fractions[COOL_ROOF].iloc[0] + fractions[GREEN_ROOF].iloc[0]
    assert treated_roof <= 0.5 + 1e-9


@pytest.mark.integration
def test_duplicate_intervention_types_are_rejected(cfg):
    with pytest.raises(ValueError, match="ganda"):
        treated_fractions(
            _one_cell(),
            [
                Intervention(TREE, {"canopy_increase_pp": 1.0}),
                Intervention(TREE, {"canopy_increase_pp": 2.0}),
            ],
            cfg,
        )


# --- feature deltas ------------------------------------------------------------------

@pytest.mark.integration
def test_apply_interventions_does_not_mutate_its_input(cells, cfg):
    before = cells["tree_frac"].copy()
    apply_interventions(cells, [from_level(TREE, "high")], cfg)
    pd.testing.assert_series_equal(cells["tree_frac"], before)


@pytest.mark.integration
def test_planting_raises_canopy_and_greenness(cells, cfg):
    after = apply_interventions(cells, [from_level(TREE, "high")], cfg)
    assert (after["tree_frac"] >= cells["tree_frac"]).all()
    assert (after["ndvi"] >= cells["ndvi"] - 1e-12).all()


@pytest.mark.integration
def test_planting_never_pushes_ndvi_above_the_calibrated_tree_value(cells, cfg):
    ndvi_tree = cfg["tree_planting"]["ndvi_tree"]["value"]
    after = apply_interventions(cells, [from_level(TREE, "high")], cfg)
    assert after["ndvi"].max() <= max(ndvi_tree, cells["ndvi"].max()) + 1e-9


@pytest.mark.integration
def test_cool_roof_raises_albedo(cells, cfg):
    after = apply_interventions(cells, [from_level(COOL_ROOF, "high")], cfg)
    assert (after["albedo"] >= cells["albedo"]).all()


@pytest.mark.integration
def test_feature_fractions_stay_physically_bounded(cells, cfg):
    after = apply_interventions(
        cells,
        [from_level(TREE, "high"), from_level(COOL_ROOF, "high"), from_level(GREEN_ROOF, "high")],
        cfg,
    )
    for column in ("tree_frac", "built_frac", "water_frac", "roof_frac", "albedo", "ndvi"):
        assert after[column].between(0.0, 1.0).all(), f"{column} keluar dari [0,1]"


# --- the mandatory sign guarantees ---------------------------------------------------

@pytest.mark.integration
def test_planting_trees_never_warms_a_kelurahan(trained, cells, cfg, costs):
    # CLAUDE.md names this test explicitly.
    booster, frame = trained
    q99 = training_quantiles(frame)
    for level in ("low", "medium", "high"):
        result = simulate(cells, [from_level(TREE, level)], booster, cfg, costs, q99)
        assert result.delta_lst_c <= 1e-9, f"pohon level {level} menaikkan LST"


@pytest.mark.integration
def test_cool_roof_never_warms_a_kelurahan(trained, cells, cfg, costs):
    booster, frame = trained
    q99 = training_quantiles(frame)
    for level in ("low", "medium", "high"):
        result = simulate(cells, [from_level(COOL_ROOF, level)], booster, cfg, costs, q99)
        assert result.delta_lst_c <= 1e-9, f"cool roof level {level} menaikkan LST"


@pytest.mark.integration
def test_doing_nothing_changes_nothing(trained, cells, cfg, costs):
    booster, frame = trained
    result = simulate(cells, [], booster, cfg, costs, training_quantiles(frame))
    assert result.delta_lst_c == pytest.approx(0.0, abs=1e-12)
    assert result.cost_idr == 0.0


@pytest.mark.integration
def test_a_stronger_intervention_cools_at_least_as_much(trained, cells, cfg, costs):
    booster, frame = trained
    q99 = training_quantiles(frame)
    low = simulate(cells, [from_level(TREE, "low")], booster, cfg, costs, q99)
    high = simulate(cells, [from_level(TREE, "high")], booster, cfg, costs, q99)
    assert high.delta_lst_c <= low.delta_lst_c + 1e-9


# --- extrapolation flag ---------------------------------------------------------------

@pytest.mark.integration
def test_an_absurd_scenario_is_flagged_as_extrapolation(trained, cells, cfg, costs):
    # CLAUDE.md: "ekstrapolasi diberi flag". Pushing albedo far past anything in the
    # training data must be reported, not silently predicted.
    booster, frame = trained
    loud = cells.copy()
    loud["roof_frac"] = 1.0

    result = simulate(
        loud,
        [Intervention(COOL_ROOF, {"adoption_rate": 1.0})],
        booster,
        cfg,
        costs,
        training_quantiles(frame),
    )

    assert result.extrapolation is True
    assert result.extrapolated_features


@pytest.mark.integration
def test_a_modest_scenario_is_not_flagged(trained, cells, cfg, costs):
    booster, frame = trained
    result = simulate(
        cells, [from_level(TREE, "low")], booster, cfg, costs, training_quantiles(frame)
    )
    assert result.extrapolation is False


@pytest.mark.integration
def test_training_quantiles_cover_every_model_feature(trained):
    _, frame = trained
    assert set(training_quantiles(frame).index) == set(FEATURES)


# --- result bookkeeping ---------------------------------------------------------------

@pytest.mark.integration
def test_result_reports_the_kelurahan_and_cell_count(trained, cells, cfg, costs):
    booster, frame = trained
    result = simulate(
        cells, [from_level(TREE, "low")], booster, cfg, costs, training_quantiles(frame)
    )
    assert result.kel_id == "ID3173040002"
    assert result.n_cells == len(cells)


@pytest.mark.integration
def test_simulate_rejects_a_mixed_kelurahan_frame(trained, fixture_store, cfg, costs):
    booster, frame = trained
    with pytest.raises(ValueError, match="satu kelurahan"):
        simulate(
            fixture_store.grid, [from_level(TREE, "low")], booster, cfg, costs,
            training_quantiles(frame),
        )


@pytest.mark.integration
def test_area_billed_equals_area_simulated(trained, cells, cfg, costs):
    # The whole point of sharing treated_fractions(): a planner must never be charged for
    # more square metres than the model was told about.
    booster, frame = trained
    interventions = [from_level(TREE, "medium"), from_level(COOL_ROOF, "medium")]
    result = simulate(cells, interventions, booster, cfg, costs, training_quantiles(frame))
    areas = intervened_area_m2(cells, interventions, cfg)
    assert result.area_m2 == pytest.approx(sum(areas.values()))
    assert set(result.area_by_type) == set(areas)


@pytest.mark.integration
def test_cost_sources_are_carried_so_facts_can_cite_them(trained, cells, cfg, costs):
    # Kampung Rawa is 100 % built in the fixture, so tree planting has zero plantable area.
    # cool_roof treats the roof that exists, so it is the intervention that actually bills here.
    booster, frame = trained
    result = simulate(
        cells, [from_level(COOL_ROOF, "low")], booster, cfg, costs, training_quantiles(frame)
    )
    assert result.cost_idr > 0
    assert result.cost_sources, "biaya tanpa source tidak boleh lolos (CLAUDE.md aturan 4)"


@pytest.mark.integration
def test_vulnerable_benefiting_never_exceeds_the_vulnerable_population(
    trained, cells, cfg, costs
):
    booster, frame = trained
    result = simulate(
        cells, [from_level(TREE, "high")], booster, cfg, costs, training_quantiles(frame)
    )
    total_vulnerable = (cells["pop_u5"].fillna(0) + cells["pop_65p"].fillna(0)).sum()
    assert result.vulnerable_benefiting <= total_vulnerable + 1e-6


@pytest.mark.integration
def test_population_weighted_delta_is_finite_even_with_unpopulated_cells(
    trained, cells, cfg, costs
):
    # 1_207 good cells have NaN pop. A naive weighted mean returns NaN and the UI would
    # print "NaN °C" to a planner.
    booster, frame = trained
    empty = cells.copy()
    empty["pop"] = np.nan
    result = simulate(
        empty, [from_level(TREE, "low")], booster, cfg, costs, training_quantiles(frame)
    )
    assert np.isfinite(result.delta_lst_pop_weighted_c)
