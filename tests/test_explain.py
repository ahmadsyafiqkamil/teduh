"""SHAP is what the drawer's "Apa yang membuat wilayah ini panas?" panel renders, and
design/README.md requires the contributions to sum to the stated difference. The additivity
test is therefore a product requirement, not a statistics nicety."""

import pytest

from model.explain import SHAP_PREFIX, by_kelurahan, shap_values, top_drivers
from model.train import FEATURES, fit_final, prepare


@pytest.fixture(scope="module")
def trained(fixture_store):
    frame = prepare(fixture_store.grid)
    return fit_final(frame), frame


@pytest.mark.integration
def test_shap_matrix_has_one_column_per_feature(trained):
    booster, frame = trained
    assert shap_values(booster, frame).shape == (len(frame), len(FEATURES))


@pytest.mark.integration
def test_shap_contributions_are_additive_against_the_prediction(trained):
    # FR3.3: base value plus every contribution must equal the model prediction, or the
    # divergent bar chart in the drawer is lying about its own total.
    booster, frame = trained
    table = by_kelurahan(booster, frame)
    contributions = table[[f"{SHAP_PREFIX}{name}" for name in FEATURES]].sum(axis=1)
    reconstructed = table["base_value"] + contributions
    assert (reconstructed - table["pred_lst_c"]).abs().max() < 0.01


@pytest.mark.integration
def test_one_row_per_kelurahan(trained):
    booster, frame = trained
    table = by_kelurahan(booster, frame)
    assert len(table) == frame["kel_id"].nunique()
    assert table["kel_id"].is_unique


@pytest.mark.integration
def test_cell_counts_are_conserved(trained):
    booster, frame = trained
    assert by_kelurahan(booster, frame)["n_cells"].sum() == len(frame)


@pytest.mark.integration
def test_bare_kelurahan_is_not_cooled_by_canopy_it_does_not_have(trained):
    # Kampung Rawa has tree_frac 0.000 and the highest HVI in Jakarta. With a -1 monotonic
    # constraint on tree_frac, having none of it cannot be a cooling contribution.
    booster, frame = trained
    table = by_kelurahan(booster, frame).set_index("kel_id")
    if "ID3173040002" not in table.index:
        pytest.skip("Kampung Rawa tidak ada di fixture")
    assert table.loc["ID3173040002", f"{SHAP_PREFIX}tree_frac"] >= 0


@pytest.mark.integration
def test_top_drivers_returns_at_most_the_requested_number_sorted_by_magnitude(trained):
    booster, frame = trained
    row = by_kelurahan(booster, frame).iloc[0]

    drivers = top_drivers(row, limit=3)

    assert len(drivers) <= 3
    magnitudes = [abs(d["contribution_c"]) for d in drivers]
    assert magnitudes == sorted(magnitudes, reverse=True)


@pytest.mark.integration
def test_top_drivers_labels_direction_in_indonesian(trained):
    booster, frame = trained
    row = by_kelurahan(booster, frame).iloc[0]
    for driver in top_drivers(row):
        assert driver["direction"] in {"memanaskan", "mendinginkan"}
        assert driver["feature"] in FEATURES
