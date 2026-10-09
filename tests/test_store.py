"""The store is the runtime's only door to data. If it loads the wrong thing quietly, every
number downstream is wrong with full confidence, so these tests pin the shape and the
provenance rule rather than any particular value."""

import pytest

from teduh_agent.store import CITY_LST_FALLBACK, config_entry, good_cells


@pytest.mark.integration
def test_fixture_store_loads_three_kelurahan_indexed_by_kel_id(fixture_store):
    assert len(fixture_store.kelurahan) == 3
    assert fixture_store.kelurahan.index.name == "kel_id"
    assert "ID3173040002" in fixture_store.kelurahan.index


@pytest.mark.integration
def test_grid_is_indexed_by_cell_id(fixture_store):
    assert fixture_store.grid.index.name == "cell_id"
    assert len(fixture_store.grid) == 173


@pytest.mark.integration
def test_city_lst_mean_is_computed_from_good_cells_only(fixture_store):
    # A "low" quality cell has fewer than 20 clean observations and skews hot
    # (DECISIONS 2026-10-09), so including it would bias the city baseline upward.
    expected = good_cells(fixture_store.grid)["lst_c"].mean()
    assert fixture_store.city_lst_mean == pytest.approx(expected)


@pytest.mark.integration
def test_good_cells_excludes_low_quality_rows(fixture_store):
    assert (good_cells(fixture_store.grid)["lst_quality"] == "good").all()


@pytest.mark.integration
def test_boundaries_carry_the_six_naming_properties(fixture_store):
    props = fixture_store.boundaries["features"][0]["properties"]
    assert set(props) == {"kel_id", "kel_name", "kec_id", "kec_name", "kota_id", "kota_name"}


@pytest.mark.integration
def test_config_entry_returns_both_value_and_source(fixture_store):
    value, source = config_entry(fixture_store.costs_cfg, "cool_roof", "cost_idr_per_m2")
    assert value == 95000
    assert source == "ASUMSI"


@pytest.mark.integration
def test_config_entry_returns_a_citation_for_a_sourced_price(fixture_store):
    value, source = config_entry(fixture_store.costs_cfg, "tree_planting", "tree_unit_idr")
    assert value == 2702703
    assert "Kepgub" in source


@pytest.mark.unit
def test_config_entry_rejects_an_entry_without_a_source():
    # CLAUDE.md rule 4: every constant carries a source. Enforced at read time so a
    # source-less entry can never silently become a number in a brief.
    with pytest.raises(KeyError, match="source"):
        config_entry({"cool_roof": {"value": 1}}, "cool_roof")


@pytest.mark.unit
def test_config_entry_names_the_missing_path():
    with pytest.raises(KeyError, match="green_roof.tidak_ada"):
        config_entry({"green_roof": {}}, "green_roof", "tidak_ada")


@pytest.mark.integration
def test_every_evidence_entry_is_citable(fixture_store):
    # interventions.json is explicit: verified=false means the figure has not been read back
    # to its source yet and "must not be presented as evidence". Those entries are allowed to
    # lack a url_or_doi; only verified entries must be citable.
    assert len(fixture_store.evidence) == 10
    for entry in fixture_store.evidence:
        assert entry["id"]
        assert entry["intervention"]
        assert entry["metric"]
        if entry["verified"]:
            assert entry["url_or_doi"], f"{entry['id']} tidak punya url_or_doi"


@pytest.mark.integration
def test_model_artifacts_are_optional_before_m2(fixture_store):
    # api/ and teduh_agent/tools/ must import cleanly before model/train.py has ever run.
    assert fixture_store.booster is None or hasattr(fixture_store.booster, "predict")
    assert fixture_store.shap_by_kel is None or "kel_id" in fixture_store.shap_by_kel.columns


@pytest.mark.integration
def test_real_store_has_all_264_kelurahan(real_store):
    assert len(real_store.kelurahan) == 264
    assert len(real_store.grid) == 75_636
    assert real_store.city_lst_mean == pytest.approx(CITY_LST_FALLBACK, abs=1e-3)
