"""Guards the three non-negotiables of CONCEPT §7.3: no coordinates as features, monotonic
constraints actually applied, and blocks that are spatial rather than random. The full
75k-cell training run is exercised by `uv run python -m model.train`, not here -- these tests
train a tiny model on the 173-cell fixture so they stay fast."""

import numpy as np
import pandas as pd
import pytest

from model.train import (
    FEATURES,
    MONOTONE,
    TARGET,
    fit_final,
    monotone_constraints,
    predict,
    prepare,
    spatial_blocks,
    summarise,
)


def _synthetic_row(**overrides) -> dict:
    """One complete feature row, so a test can vary exactly one thing."""
    row = {name: 0.1 for name in FEATURES}
    row.update({"lst_c": 40.0, "lst_quality": "good", "lon": 106.8, "lat": -6.2})
    row.update(overrides)
    return row


@pytest.mark.unit
def test_features_never_include_coordinates():
    # CLAUDE.md rule 5. With lon/lat the model memorises geography and the scenario engine
    # stops responding to tree_frac, which silently guts the whole product.
    assert "lon" not in FEATURES
    assert "lat" not in FEATURES


@pytest.mark.unit
def test_features_exclude_leaky_and_outcome_columns():
    for forbidden in ("lst_c", "lst_n", "lst_quality", "hvi", "kel_id", "pop_u5", "pop_65p"):
        assert forbidden not in FEATURES


@pytest.mark.unit
def test_monotone_constraints_align_positionally_with_features():
    constraints = monotone_constraints()
    assert len(constraints) == len(FEATURES)
    for name, sign in MONOTONE.items():
        assert constraints[FEATURES.index(name)] == sign


@pytest.mark.unit
def test_cooling_features_are_constrained_downward():
    for name in ("ndvi", "albedo", "tree_frac", "water_frac"):
        assert MONOTONE[name] == -1


@pytest.mark.unit
def test_warming_features_are_constrained_upward():
    for name in ("built_frac", "ndbi"):
        assert MONOTONE[name] == 1


@pytest.mark.unit
def test_unconstrained_features_get_zero():
    constraints = monotone_constraints()
    assert constraints[FEATURES.index("elev_m")] == 0
    assert constraints[FEATURES.index("dist_coast_km")] == 0


@pytest.mark.unit
def test_spatial_blocks_group_neighbours_and_split_distant_cells():
    # Two cells ~100 m apart belong in one 1 km block; one ~5 km away must not.
    frame = pd.DataFrame(
        {"lon": [106.800, 106.801, 106.850], "lat": [-6.200, -6.200, -6.200]}
    )
    blocks = spatial_blocks(frame)
    assert blocks.iloc[0] == blocks.iloc[1]
    assert blocks.iloc[0] != blocks.iloc[2]


@pytest.mark.integration
def test_spatial_blocks_produce_enough_groups_for_five_folds(fixture_store):
    assert spatial_blocks(fixture_store.grid).nunique() >= 5


@pytest.mark.unit
def test_prepare_drops_rows_without_a_target():
    frame = pd.DataFrame([_synthetic_row(), _synthetic_row(lst_c=np.nan)])
    assert len(prepare(frame)) == 1


@pytest.mark.unit
def test_prepare_fills_missing_population_with_zero():
    # WorldPop is a constrained model: a NaN means it placed nobody there, not that the
    # value is unknown. Dropping those rows would throw away valid thermal signal.
    frame = pd.DataFrame([_synthetic_row(pop=np.nan)])
    assert prepare(frame)["pop"].iloc[0] == 0.0


@pytest.mark.unit
def test_prepare_excludes_low_quality_cells():
    frame = pd.DataFrame(
        [_synthetic_row(), _synthetic_row(lst_c=55.0, lst_quality="low", lon=106.9)]
    )
    prepared = prepare(frame)
    assert len(prepared) == 1
    assert prepared[TARGET].iloc[0] == 40.0


@pytest.mark.unit
def test_summarise_reports_the_worst_fold_not_only_the_mean():
    # A good mean hiding one terrible fold is exactly the spatial-CV failure worth seeing.
    folds = [
        {"fold": 0, "r2": 0.90, "rmse": 1.0, "mae": 0.8, "n_train": 1, "n_test": 1},
        {"fold": 1, "r2": 0.50, "rmse": 2.0, "mae": 1.6, "n_train": 1, "n_test": 1},
    ]
    summary = summarise(folds)
    assert summary["r2_mean"] == pytest.approx(0.70)
    assert summary["r2_min"] == pytest.approx(0.50)


@pytest.mark.integration
def test_monotonic_constraints_hold_on_a_model_trained_from_the_fixture(fixture_store):
    # The behavioural guarantee tests/test_scenario.py depends on: more canopy, more
    # greenness, more albedo must never raise the predicted surface temperature.
    frame = prepare(fixture_store.grid)
    booster = fit_final(frame)

    probe = frame.head(20).copy()
    base = predict(booster, probe)

    for name in ("ndvi", "tree_frac", "albedo", "water_frac"):
        greener = probe.copy()
        greener[name] = (greener[name] + 0.2).clip(upper=1.0)
        assert (predict(booster, greener) <= base + 1e-9).all(), (
            f"menaikkan {name} menaikkan prediksi LST -- monotonic constraint tidak terpasang"
        )


@pytest.mark.integration
def test_predict_uses_only_the_declared_feature_columns(fixture_store):
    frame = prepare(fixture_store.grid)
    booster = fit_final(frame)
    noisy = frame.head(5).copy()
    noisy["lon"] = 0.0
    noisy["lat"] = 0.0
    assert np.allclose(predict(booster, frame.head(5)), predict(booster, noisy))
