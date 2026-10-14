"""These four tools answer nine of the twenty golden questions, so their names and their
facts contract are load-bearing. The fuzzy-search tests matter more than they look: a planner
types "Jakarta Timur", and kota_name lives only in the GeoJSON, not in the metrics parquet."""

import pytest

from teduh_agent.tools.areas import (
    DEFAULT_TOP_K,
    MAX_TOP_K,
    SCOPE_ALL,
    explain_drivers,
    find_area,
    get_area_profile,
    rank_priority_areas,
)


class FakeToolContext:
    def __init__(self) -> None:
        self.state: dict = {}


def _fact_ids(result: dict) -> set[str]:
    return {f["id"] for f in result["facts"]}


# --- find_area -----------------------------------------------------------------------

@pytest.mark.integration
def test_find_area_matches_an_exact_kelurahan_name():
    result = find_area("Kampung Rawa")
    assert result["scope_type"] == "kelurahan"
    assert any(m["kel_id"] == "ID3173040002" for m in result["matches"])


@pytest.mark.integration
def test_find_area_is_case_and_space_insensitive():
    assert find_area("  kampung rawa ")["matches"][0]["kel_id"] == "ID3173040002"


@pytest.mark.integration
def test_find_area_tolerates_a_typo():
    # Planners type fast. "Kampong Rawa" must still land.
    result = find_area("Kampong Rawa")
    assert any(m["kel_id"] == "ID3173040002" for m in result["matches"])


@pytest.mark.integration
def test_find_area_resolves_a_kota_to_all_its_kelurahan():
    # kota_name only exists in data/boundaries/kelurahan.geojson, so this fails outright
    # if directory() forgets to join the boundary properties.
    result = find_area("Jakarta Timur")
    assert result["scope_type"] == "kota"
    assert result["scope_id"] == "ID3172"
    assert len(result["matches"]) > 50


@pytest.mark.integration
def test_find_area_resolves_a_kecamatan():
    result = find_area("Pademangan")
    assert result["scope_type"] == "kecamatan"
    assert all(m["kec_name"] == "Pademangan" for m in result["matches"])


@pytest.mark.integration
def test_find_area_strips_an_administrative_prefix():
    assert find_area("Kec. Pademangan")["scope_type"] == "kecamatan"


@pytest.mark.integration
def test_find_area_reports_no_match_without_inventing_one():
    result = find_area("Bandung")
    assert result["matches"] == []
    assert "error" in result
    assert result["facts"] == []


@pytest.mark.integration
def test_find_area_records_a_fact_for_the_match_count():
    ctx = FakeToolContext()
    find_area("Jakarta Pusat", ctx)
    assert any(f["id"].startswith("find.") for f in ctx.state["facts"])


# --- get_area_profile ----------------------------------------------------------------

@pytest.mark.integration
def test_profile_returns_every_metric_the_drawer_renders():
    result = get_area_profile("ID3173040002")
    expected = {
        "kel_ID3173040002.lst",
        "kel_ID3173040002.lst_anomaly",
        "kel_ID3173040002.hvi",
        "kel_ID3173040002.hvi_rank",
        "kel_ID3173040002.ndvi",
        "kel_ID3173040002.tree_frac",
        "kel_ID3173040002.built_frac",
        "kel_ID3173040002.pop",
        "kel_ID3173040002.vulnerable",
        "kel_ID3173040002.exposed_vulnerable",
        "kel_ID3173040002.H",
        "kel_ID3173040002.E",
        "kel_ID3173040002.S",
        "kel_ID3173040002.A",
    }
    assert expected <= _fact_ids(result)


@pytest.mark.integration
def test_profile_anomaly_is_measured_against_the_city_mean(real_store):
    result = get_area_profile("ID3173040002")
    facts = {f["id"]: f["value"] for f in result["facts"]}
    expected = real_store.kelurahan.loc["ID3173040002", "lst_c_mean"] - real_store.city_lst_mean
    assert facts["kel_ID3173040002.lst_anomaly"] == pytest.approx(expected, abs=0.01)


@pytest.mark.integration
def test_profile_states_total_kelurahan_so_a_rank_is_interpretable():
    result = get_area_profile("ID3173040002")
    assert result["total_kelurahan"] == 264


@pytest.mark.integration
def test_profile_every_numeric_fact_carries_a_source():
    for entry in get_area_profile("ID3173040002")["facts"]:
        assert entry["source"], f"{entry['id']} tanpa source"


@pytest.mark.integration
def test_profile_labels_lst_as_surface_temperature():
    labels = {f["id"]: f["label"] for f in get_area_profile("ID3173040002")["facts"]}
    assert "permukaan" in labels["kel_ID3173040002.lst"].lower()


@pytest.mark.integration
def test_profile_highlights_the_kelurahan_on_the_map():
    assert get_area_profile("ID3173040002")["map_highlight"] == ["ID3173040002"]


@pytest.mark.integration
def test_profile_rejects_an_unknown_kelurahan_without_guessing():
    result = get_area_profile("ID9999999999")
    assert "error" in result
    assert result["facts"] == []


# --- rank_priority_areas -------------------------------------------------------------

@pytest.mark.integration
def test_ranking_all_of_jakarta_puts_kampung_rawa_first():
    result = rank_priority_areas(SCOPE_ALL, top_k=5)
    assert result["areas"][0]["kel_id"] == "ID3173040002"


@pytest.mark.integration
def test_ranking_returns_exactly_top_k_areas():
    assert len(rank_priority_areas(SCOPE_ALL, top_k=3)["areas"]) == 3


@pytest.mark.integration
def test_ranking_defaults_to_ten():
    assert len(rank_priority_areas()["areas"]) == DEFAULT_TOP_K


@pytest.mark.integration
def test_ranking_caps_an_absurd_top_k():
    result = rank_priority_areas(SCOPE_ALL, top_k=10_000)
    assert len(result["areas"]) <= MAX_TOP_K


@pytest.mark.integration
def test_narrowing_the_scope_does_not_change_a_reported_hvi():
    """CONCEPT 7.4 normalises every component to a percentile *within the city*. If the tool
    re-percentiles inside the scope, the chat reports one HVI while the map paints another, and
    the two contradict each other on screen in the same frame."""
    from teduh_agent.store import get_store

    stored = get_store().kelurahan.loc["ID3173040002", "hvi"]
    scoped = rank_priority_areas("Kota Jakarta Pusat", top_k=5)
    reported = next(a["hvi"] for a in scoped["areas"] if a["kel_id"] == "ID3173040002")
    assert reported == pytest.approx(float(stored), abs=1e-9)


@pytest.mark.integration
def test_narrowing_the_scope_does_not_reorder_the_ranking():
    citywide = rank_priority_areas(SCOPE_ALL, top_k=MAX_TOP_K)
    in_jakpus = [a["kel_id"] for a in citywide["areas"] if a["kota_id"] == "ID3173"][:3]
    scoped = [a["kel_id"] for a in rank_priority_areas("Kota Jakarta Pusat", top_k=3)["areas"]]
    assert scoped == in_jakpus


@pytest.mark.integration
def test_ranking_can_be_narrowed_to_one_kota():
    result = rank_priority_areas("ID3172", top_k=5)
    assert all(area["kota_id"] == "ID3172" for area in result["areas"])


@pytest.mark.integration
def test_ranking_accepts_a_kota_name_not_only_a_code():
    # The agent will pass whatever the user said.
    result = rank_priority_areas("Jakarta Timur", top_k=5)
    assert all(area["kota_id"] == "ID3172" for area in result["areas"])


@pytest.mark.integration
def test_ranking_highlights_the_same_areas_it_returned():
    result = rank_priority_areas(SCOPE_ALL, top_k=5)
    assert result["map_highlight"] == [area["kel_id"] for area in result["areas"]]


@pytest.mark.integration
def test_custom_weights_change_the_ordering_and_are_reported():
    # The planner's weights go into the brief, so the tool must state what it used.
    canopy_first = rank_priority_areas(SCOPE_ALL, top_k=10, weights={"wE": 0.0, "wS": 0.0,
                                                                     "wA": 1.0})
    default = rank_priority_areas(SCOPE_ALL, top_k=10)
    assert canopy_first["weights"] == {"wE": 0.0, "wS": 0.0, "wA": 1.0}
    assert [a["kel_id"] for a in canopy_first["areas"]] != [a["kel_id"] for a in default["areas"]]


@pytest.mark.integration
def test_ranking_with_recomputed_weights_still_reports_a_rank_within_the_scope():
    result = rank_priority_areas(SCOPE_ALL, top_k=3, weights={"wE": 0.5, "wS": 0.5, "wA": 0.0})
    assert [area["rank"] for area in result["areas"]] == [1, 2, 3]


@pytest.mark.integration
def test_ranking_rejects_a_negative_weight_from_the_ui():
    result = rank_priority_areas(SCOPE_ALL, weights={"wE": -1.0, "wS": 1.0, "wA": 1.0})
    assert "error" in result
    assert result["facts"] == []


@pytest.mark.integration
def test_ranking_rejects_an_unknown_scope():
    result = rank_priority_areas("Surabaya")
    assert "error" in result


@pytest.mark.integration
def test_ranking_emits_a_fact_per_returned_area():
    result = rank_priority_areas(SCOPE_ALL, top_k=3)
    ids = _fact_ids(result)
    assert "rank.all.1.hvi" in ids
    assert "rank.all.3.hvi" in ids


# --- explain_drivers -----------------------------------------------------------------

@pytest.mark.integration
def test_drivers_returns_between_one_and_five_factors():
    result = explain_drivers("ID3173040002")
    if "error" in result:
        pytest.skip("shap_by_kel.parquet belum dibuat; jalankan model.explain")
    assert 1 <= len(result["drivers"]) <= 5


@pytest.mark.integration
def test_drivers_are_labelled_in_indonesian_with_a_direction():
    result = explain_drivers("ID3173040002")
    if "error" in result:
        pytest.skip("shap_by_kel.parquet belum dibuat")
    for driver in result["drivers"]:
        assert driver["direction"] in {"memanaskan", "mendinginkan"}
        assert driver["label"], "fitur model tanpa label Bahasa Indonesia"


@pytest.mark.integration
def test_drivers_are_sourced_to_the_model_not_the_data():
    result = explain_drivers("ID3173040002")
    if "error" in result:
        pytest.skip("shap_by_kel.parquet belum dibuat")
    for entry in result["facts"]:
        if entry["id"].startswith("driver."):
            assert entry["source"] == "model:lgbm@v1"


@pytest.mark.integration
def test_drivers_says_so_plainly_when_shap_is_missing(monkeypatch):
    # CLAUDE.md: if the data is not there, say it is not there.
    import teduh_agent.tools.areas as areas_module

    class _StoreWithoutShap:
        shap_by_kel = None
        booster = None

        def __init__(self) -> None:
            from teduh_agent.store import load

            self._real = load()

        def __getattr__(self, name):
            return getattr(self._real, name)

    monkeypatch.setattr(areas_module, "get_store", lambda: _StoreWithoutShap())
    result = explain_drivers("ID3173040002")
    assert "error" in result
    assert result["facts"] == []
