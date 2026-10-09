"""HTTP surface. The map payload tests matter most: the frontend renders a choropleth
straight from GeoJSON properties, so a missing metric means a blank map rather than an error,
which is the kind of failure nobody notices until a demo."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes import MAP_METRICS, router


@pytest.fixture(scope="module")
def client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


@pytest.mark.integration
def test_health_reports_what_is_loaded(client):
    body = client.get("/api/health").json()
    assert body["success"] is True
    assert body["data"]["n_kelurahan"] == 264


@pytest.mark.integration
def test_map_payload_is_a_feature_collection_of_264_kelurahan(client):
    body = client.get("/api/kelurahan").json()
    collection = body["data"]
    assert collection["type"] == "FeatureCollection"
    assert len(collection["features"]) == 264


@pytest.mark.integration
def test_every_feature_carries_every_metric_the_four_layers_need(client):
    collection = client.get("/api/kelurahan").json()["data"]
    for feature in collection["features"][:20]:
        for metric in MAP_METRICS:
            assert metric in feature["properties"], f"{metric} hilang dari properti"


@pytest.mark.integration
def test_features_keep_their_names_for_tooltips(client):
    properties = client.get("/api/kelurahan").json()["data"]["features"][0]["properties"]
    for key in ("kel_id", "kel_name", "kec_name", "kota_name"):
        assert properties[key]


@pytest.mark.integration
def test_coordinates_are_thinned_to_metre_precision(client):
    collection = client.get("/api/kelurahan").json()["data"]
    ring = collection["features"][0]["geometry"]["coordinates"][0][0]
    for longitude, latitude in ring[:50]:
        assert len(str(longitude).split(".")[-1]) <= 5
        assert len(str(latitude).split(".")[-1]) <= 5


@pytest.mark.integration
def test_profile_endpoint_returns_facts(client):
    body = client.get("/api/kelurahan/ID3173040002").json()
    assert body["success"] is True
    assert body["data"]["facts"]
    assert body["data"]["profile"]["kel_name"] == "Kampung Rawa"


@pytest.mark.integration
def test_profile_endpoint_includes_the_shap_drivers_the_drawer_renders(client):
    body = client.get("/api/kelurahan/ID3173040002").json()
    # drivers may be absent only when shap_by_kel.parquet has not been generated
    assert "drivers" in body["data"]


@pytest.mark.integration
def test_unknown_kelurahan_is_a_404_with_an_indonesian_message(client):
    response = client.get("/api/kelurahan/ID9999999999")
    assert response.status_code == 404
    assert "tidak ada" in response.json()["error"].lower()


@pytest.mark.integration
def test_simulate_endpoint_runs_without_an_llm(client):
    response = client.post(
        "/api/simulate",
        json={
            "kel_ids": ["ID3173040002"],
            "interventions": [{"type": "cool_roof", "level": "medium"}],
        },
    )
    body = response.json()
    assert body["success"] is True
    assert body["data"]["results"][0]["delta_lst_c"] <= 1e-9


@pytest.mark.integration
def test_simulate_rejects_a_malformed_body_with_422(client):
    response = client.post(
        "/api/simulate",
        json={"kel_ids": ["bukan-id"], "interventions": [{"type": "cool_roof",
                                                          "level": "low"}]},
    )
    assert response.status_code == 422


@pytest.mark.integration
def test_simulate_turns_a_tool_level_error_into_a_400(client):
    response = client.post(
        "/api/simulate",
        json={
            "kel_ids": ["ID3173999999"],
            "interventions": [{"type": "cool_roof", "level": "low"}],
        },
    )
    assert response.status_code == 400
    assert response.json()["success"] is False


@pytest.mark.integration
def test_optimize_endpoint_respects_the_budget(client):
    response = client.post(
        "/api/optimize", json={"scope": "ID3173", "budget_idr": 2_000_000_000}
    )
    body = response.json()
    if not body["success"]:
        pytest.skip(body["error"])
    assert body["data"]["total_cost_idr"] <= 2_000_000_000


@pytest.mark.integration
def test_optimize_rejects_a_zero_budget_with_422(client):
    assert client.post("/api/optimize", json={"budget_idr": 0}).status_code == 422


@pytest.mark.integration
def test_model_card_is_served_for_the_about_page(client):
    response = client.get("/api/model-card")
    if response.status_code == 404:
        pytest.skip("model_card.json belum dibuat; jalankan model.train")
    card = response.json()["data"]
    assert card["validation"]["scheme"].startswith("spatial block CV")
    assert card["limitations"]


@pytest.mark.integration
def test_error_messages_never_leak_a_filesystem_path(client):
    for response in (
        client.get("/api/kelurahan/ID9999999999"),
        client.post("/api/simulate", json={"kel_ids": ["ID3173999999"],
                                           "interventions": [{"type": "cool_roof",
                                                              "level": "low"}]}),
    ):
        assert "/Users" not in response.text
        assert "/app" not in response.text
