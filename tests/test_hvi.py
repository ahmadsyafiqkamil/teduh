"""HVI drives which kelurahan get money. The regression test against the committed
kelurahan_metrics.parquet column is the important one here: it proves the extracted formula
is the same arithmetic the pipeline already baked in, so the map and a runtime re-ranking can
never disagree about who is most vulnerable."""

import pandas as pd
import pytest

from model.hvi import (
    COMPONENT_COLUMNS,
    DEFAULT_WEIGHTS,
    components,
    hvi,
    load_weights,
    percentile,
    rank,
)


@pytest.fixture
def toy_kelurahan() -> pd.DataFrame:
    """Three kelurahan spanning the range: hot-dense-bare, middling, cool-leafy."""
    return pd.DataFrame(
        {
            "lst_c_mean": [44.6, 42.4, 39.2],
            "pop_density": [30_000.0, 20_000.0, 9_000.0],
            "vulnerable_share": [0.18, 0.12, 0.08],
            "tree_frac_mean": [0.000, 0.083, 0.495],
        },
        index=pd.Index(["ID_HOT", "ID_MID", "ID_COOL"], name="kel_id"),
    )


@pytest.mark.unit
def test_percentile_is_bounded_and_monotone():
    result = percentile(pd.Series([10.0, 20.0, 30.0]))
    assert result.between(0.0, 1.0).all()
    assert result.is_monotonic_increasing


@pytest.mark.unit
def test_percentile_keeps_nan_instead_of_inventing_a_middling_value():
    # A NaN turned into 0.5 would quietly rank an unmeasured kelurahan as average.
    result = percentile(pd.Series([10.0, None, 30.0]))
    assert result.isna().sum() == 1


@pytest.mark.unit
def test_components_are_all_bounded_in_the_unit_interval(toy_kelurahan):
    comp = components(toy_kelurahan)
    assert list(comp.columns) == list(COMPONENT_COLUMNS)
    for column in COMPONENT_COLUMNS:
        assert comp[column].between(0.0, 1.0).all()


@pytest.mark.unit
def test_adaptive_capacity_component_is_inverted(toy_kelurahan):
    # A is "lack of adaptive capacity", so the leafiest kelurahan must score lowest.
    comp = components(toy_kelurahan)
    assert comp.loc["ID_COOL", "A"] < comp.loc["ID_HOT", "A"]


@pytest.mark.unit
def test_components_rejects_a_frame_missing_a_required_column():
    with pytest.raises(KeyError, match="tree_frac_mean"):
        components(
            pd.DataFrame(
                {"lst_c_mean": [40.0], "pop_density": [1.0], "vulnerable_share": [0.1]}
            )
        )


@pytest.mark.unit
def test_hvi_ranks_the_bare_dense_kelurahan_highest(toy_kelurahan):
    scores = hvi(components(toy_kelurahan))
    assert scores.loc["ID_HOT"] > scores.loc["ID_MID"] > scores.loc["ID_COOL"]


@pytest.mark.unit
def test_hvi_stays_in_the_unit_interval(toy_kelurahan):
    assert hvi(components(toy_kelurahan)).between(0.0, 1.0).all()


@pytest.mark.unit
def test_hvi_shifts_when_the_planner_reweights_adaptive_capacity(toy_kelurahan):
    comp = components(toy_kelurahan)
    canopy_focused = hvi(comp, {"wE": 0.0, "wS": 0.0, "wA": 1.0})
    density_focused = hvi(comp, {"wE": 1.0, "wS": 0.0, "wA": 0.0})
    assert canopy_focused.loc["ID_HOT"] != density_focused.loc["ID_HOT"]


@pytest.mark.unit
def test_hvi_rejects_incomplete_weights(toy_kelurahan):
    with pytest.raises(KeyError, match="wA"):
        hvi(components(toy_kelurahan), {"wE": 0.5, "wS": 0.5})


@pytest.mark.unit
def test_hvi_rejects_a_negative_weight(toy_kelurahan):
    # Weights come from the UI, so this is a trust boundary: a negative weight would
    # silently reward low exposure.
    with pytest.raises(ValueError, match="negatif"):
        hvi(components(toy_kelurahan), {"wE": -0.4, "wS": 0.7, "wA": 0.7})


@pytest.mark.unit
def test_rank_puts_the_most_vulnerable_first(toy_kelurahan):
    ranks = rank(hvi(components(toy_kelurahan)))
    assert ranks.loc["ID_HOT"] == 1
    assert ranks.loc["ID_COOL"] == 3


@pytest.mark.integration
def test_load_weights_reads_the_concept_defaults(fixture_store):
    assert load_weights(fixture_store.hvi_cfg) == DEFAULT_WEIGHTS


@pytest.mark.integration
def test_extracted_formula_reproduces_the_committed_hvi_column(real_store):
    # The regression guard. kelurahan_metrics.parquet was written by
    # pipeline/aggregate_kelurahan.py before this extraction; recomputing from the same
    # 264 rows must land on the same numbers or the refactor changed behaviour.
    kel = real_store.kelurahan
    recomputed = hvi(components(kel), DEFAULT_WEIGHTS)
    pd.testing.assert_series_equal(
        recomputed.sort_index(), kel["hvi"].sort_index(), check_names=False, rtol=1e-12
    )


@pytest.mark.integration
def test_extracted_rank_reproduces_the_committed_rank_column(real_store):
    kel = real_store.kelurahan
    pd.testing.assert_series_equal(
        rank(kel["hvi"]).sort_index().astype("int64"),
        kel["hvi_rank"].sort_index().astype("int64"),
        check_names=False,
    )


@pytest.mark.integration
def test_kampung_rawa_is_still_rank_one(real_store):
    # Named in tests/eval/golden_questions.yaml, so a change here breaks the eval set.
    assert real_store.kelurahan.loc["ID3173040002", "hvi_rank"] == 1
