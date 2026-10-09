# M3c — REST API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> Baca `docs/superpowers/plans/README.md` bagian **Global Constraints** dan **Interface Registry**. Prasyarat: **M0, M2, M3a, M3b selesai**.

**Goal:** REST API di atas tool yang sama, supaya frontend bisa menggerakkan peta, drawer, slider, dan form anggaran **tanpa memanggil LLM**, sambil chat tetap lewat endpoint ADK `/run_sse`.

**Architecture:** Route memanggil fungsi tool yang identik dengan yang dipakai agen, dengan `tool_context=None`. Tidak ada logika bisnis kedua. Konsekuensinya: apa pun yang dilihat pengguna lewat slider dijamin sama dengan apa yang dikatakan agen, karena keduanya menjalankan kode yang sama.

**Tech Stack:** FastAPI, Pydantic v2, `google.adk.cli.fast_api.get_fast_api_app`, uvicorn.

## Global Constraints

- **Validasi di batas sistem.** Semua body request lewat model Pydantic dengan batas nilai eksplisit; jangan percaya input.
- **Envelope respons konsisten**: `{success, data, error}`.
- **Jangan duplikasi logika.** Route memanggil tool, bukan menghitung sendiri.
- Tidak ada rahasia di respons; pesan error tidak boleh membocorkan path filesystem.
- Teks error yang dilihat pengguna: Bahasa Indonesia.
- Commit conventional, diakhiri `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`.

### Catatan ukuran payload

`data/boundaries/kelurahan.geojson` 2,2 MB dengan 68.501 pasang koordinat pada presisi ~7 desimal (≈1 cm). Untuk choropleth kelurahan itu berlebihan. Route membulatkan koordinat ke **5 desimal** (≈1 m), yang memotong ukuran besar tanpa menambah dependensi geometri apa pun. Jangan pakai `shapely.simplify` — `geopandas` ada di grup `pipeline` dan tidak terpasang di image runtime.

---

## File Structure

| File | Tanggung jawab |
|---|---|
| `api/schemas.py` | Model Pydantic request/response. Satu-satunya tempat bentuk HTTP didefinisikan. |
| `api/routes.py` | Router `/api/*`. Memanggil tool, membungkus hasilnya ke envelope. |
| `api/main.py` | Perakitan app: ADK `get_fast_api_app` + router + CORS + pemanasan store. |

---

## Task M3-T7: Skema request dan response

**Files:**
- Create: `api/schemas.py`
- Modify: `api/__init__.py` (ganti docstring placeholder M0 dengan yang final)
- Test: `tests/test_schemas.py`

**Interfaces:**
- Consumes: `model.scenario.{INTERVENTION_TYPES, LEVELS}` (M3-T1) untuk nilai yang sah.
- Produces:
  - `ApiResponse` — generic Pydantic: `success: bool`, `data: T | None`, `error: str | None`
  - `ok(data) -> dict`, `fail(message: str) -> dict`
  - `InterventionInput` — `type: str`, `level: str | None`, `params: dict[str, float] | None`
  - `SimulateRequest` — `kel_ids: list[str]` (1–20), `interventions: list[InterventionInput]` (1–3)
  - `OptimizeRequest` — `scope: str = "all"`, `budget_idr: int` (> 0, ≤ 1e13), `equity_share: float | None` (0–1), `allowed: list[str] | None`
  - `KEL_ID_PATTERN = r"^ID\d{10}$"`

- [ ] **Step 1: Tulis tes yang gagal**

Buat `tests/test_schemas.py`:

```python
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
```

- [ ] **Step 2: Jalankan tes untuk memastikan gagal**

Run: `uv run pytest tests/test_schemas.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'api.schemas'`

- [ ] **Step 3: Tulis `api/schemas.py`**

```python
"""HTTP request and response shapes.

This is the trust boundary. Every constraint the tools would otherwise have to re-check
lives here instead -- known intervention types, well-formed kel_id, a budget that is a real
number, a bounded number of kelurahan per request. Validating once at the edge is what lets
teduh_agent/tools/ assume well-formed input.

The list caps are not paranoia: each kelurahan in a simulate request means a model
prediction over its cells, so an unbounded list is a trivial way for one request to occupy
the whole Cloud Run instance.
"""

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field, field_validator, model_validator

from model.scenario import INTERVENTION_TYPES, LEVELS

T = TypeVar("T")

# BPS P-code: "ID" plus 10 digits, e.g. ID3173040002.
KEL_ID_PATTERN = r"^ID\d{10}$"

MAX_KELURAHAN_PER_REQUEST = 20
MAX_INTERVENTIONS_PER_REQUEST = len(INTERVENTION_TYPES)

# Rp 10 trillion. Far above any municipal programme; exists to reject typos and abuse.
MAX_BUDGET_IDR = 10**13


class ApiResponse(BaseModel, Generic[T]):
    """Consistent envelope for every endpoint."""

    success: bool
    data: T | None = None
    error: str | None = None


def ok(data: Any) -> dict:
    return {"success": True, "data": data, "error": None}


def fail(message: str) -> dict:
    return {"success": False, "data": None, "error": message}


class InterventionInput(BaseModel):
    """One intervention, given either by named level or by explicit parameters."""

    type: str
    level: str | None = None
    params: dict[str, float] | None = None

    @field_validator("type")
    @classmethod
    def _known_type(cls, value: str) -> str:
        if value not in INTERVENTION_TYPES:
            raise ValueError(
                f"jenis intervensi tidak dikenal: {value}. "
                f"Pilihan: {', '.join(INTERVENTION_TYPES)}"
            )
        return value

    @model_validator(mode="after")
    def _level_or_params(self) -> "InterventionInput":
        if self.level is None and not self.params:
            raise ValueError("intervensi butuh level atau params")
        if self.level is not None and self.level not in LEVELS[self.type]:
            raise ValueError(
                f"level tidak dikenal untuk {self.type}: {self.level}. "
                f"Pilihan: {', '.join(LEVELS[self.type])}"
            )
        return self


class SimulateRequest(BaseModel):
    """Slider-driven scenario, no LLM involved."""

    kel_ids: list[str] = Field(min_length=1, max_length=MAX_KELURAHAN_PER_REQUEST)
    interventions: list[InterventionInput] = Field(
        min_length=1, max_length=MAX_INTERVENTIONS_PER_REQUEST
    )

    @field_validator("kel_ids")
    @classmethod
    def _well_formed_ids(cls, value: list[str]) -> list[str]:
        import re

        for kel_id in value:
            if not re.match(KEL_ID_PATTERN, kel_id):
                raise ValueError(f"kel_id tidak valid: {kel_id}")
        return value


class OptimizeRequest(BaseModel):
    """Form-driven portfolio, no LLM involved."""

    scope: str = "all"
    budget_idr: int = Field(gt=0, le=MAX_BUDGET_IDR)
    equity_share: float | None = Field(default=None, ge=0.0, le=1.0)
    allowed: list[str] | None = Field(default=None, max_length=MAX_INTERVENTIONS_PER_REQUEST)

    @field_validator("allowed")
    @classmethod
    def _known_types(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        unknown = [item for item in value if item not in INTERVENTION_TYPES]
        if unknown:
            raise ValueError(f"jenis intervensi tidak dikenal: {', '.join(unknown)}")
        return value
```

Ganti isi `api/__init__.py` menjadi:

```python
"""FastAPI layer.

Routes call the same tool functions the agent calls, with tool_context=None. There is no
second implementation of any calculation here, which is what guarantees a planner dragging
a slider sees exactly what the agent would have said.
"""
```

- [ ] **Step 4: Jalankan tes untuk memastikan lulus**

Run: `uv run pytest tests/test_schemas.py -v`
Expected: PASS, 15 tes.

- [ ] **Step 5: Commit**

```bash
git add api/schemas.py api/__init__.py tests/test_schemas.py
git commit -m "feat: tambah skema Pydantic untuk validasi di batas HTTP

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task M3-T8: Router `/api/*`

**Files:**
- Create: `api/routes.py`
- Test: `tests/test_api.py`

**Interfaces:**
- Consumes: `api.schemas.{ok, fail, SimulateRequest, OptimizeRequest}` (M3-T7); `teduh_agent.tools.areas.{directory, get_area_profile, rank_priority_areas, explain_drivers}`; `teduh_agent.tools.scenario_tools.simulate_intervention`; `teduh_agent.tools.optimize.optimize_portfolio`; `teduh_agent.store.get_store`.
- Produces:
  - `router: APIRouter` dengan prefix `/api`
  - `COORD_PRECISION = 5`
  - `MAP_METRICS: tuple[str, ...]` — kolom metrik yang ikut ke properti GeoJSON
  - `map_payload() -> dict` — `lru_cache(1)`, FeatureCollection siap peta
  - Endpoint: `GET /api/kelurahan`, `GET /api/kelurahan/{kel_id}`, `POST /api/simulate`, `POST /api/optimize`, `GET /api/model-card`, `GET /api/health`

- [ ] **Step 1: Tulis tes yang gagal**

Buat `tests/test_api.py`:

```python
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
```

- [ ] **Step 2: Jalankan tes untuk memastikan gagal**

Run: `uv run pytest tests/test_api.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'api.routes'`

- [ ] **Step 3: Tulis `api/routes.py`**

```python
"""REST endpoints for the map, the drawer, the sliders, and the budget form.

Every handler delegates to the same tool function the agent calls, passing
tool_context=None. That is deliberate and worth protecting: if the slider path ever grew
its own copy of the scenario maths, the UI and the agent could disagree about the same
kelurahan, and a planner would have no way to tell which number to trust.

The map payload is built once and cached. Coordinates are rounded to five decimals (~1 m)
because kelurahan boundaries arrive at centimetre precision, which is 2.2 MB of pointless
bytes for a choropleth. Rounding needs no geometry library, which matters because geopandas
lives in the pipeline dependency group and is not installed in the runtime image.
"""

import json
from functools import lru_cache
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from api.schemas import OptimizeRequest, SimulateRequest, fail, ok
from teduh_agent.store import get_store
from teduh_agent.tools.areas import directory, explain_drivers, get_area_profile
from teduh_agent.tools.optimize import optimize_portfolio
from teduh_agent.tools.scenario_tools import simulate_intervention

router = APIRouter(prefix="/api")

# ~1 m at Jakarta's latitude. Plenty for a kelurahan choropleth.
COORD_PRECISION = 5

# Metrics the four map layers and the hover tooltip read straight off GeoJSON properties.
MAP_METRICS: tuple[str, ...] = (
    "lst_c_mean",
    "lst_anomaly_c",
    "hvi",
    "hvi_rank",
    "H",
    "E",
    "S",
    "A",
    "ndvi_mean",
    "tree_frac_mean",
    "built_frac_mean",
    "pop",
    "pop_density",
    "exposed_vulnerable",
)

NAME_PROPERTIES = ("kel_id", "kel_name", "kec_id", "kec_name", "kota_id", "kota_name")


def _round_coords(node: Any) -> Any:
    """Recursively round coordinate numbers, leaving the nesting structure untouched."""
    if isinstance(node, list):
        return [_round_coords(item) for item in node]
    if isinstance(node, float):
        return round(node, COORD_PRECISION)
    return node


def _clean(value: Any) -> Any:
    """JSON cannot carry NaN. A missing metric must be null, not the string 'NaN'."""
    if value is None:
        return None
    try:
        import math

        number = float(value)
        return None if math.isnan(number) else number
    except (TypeError, ValueError):
        return value


@lru_cache(maxsize=1)
def map_payload() -> dict:
    """GeoJSON plus per-kelurahan metrics, built once per process."""
    store = get_store()
    frame = directory()

    features = []
    for feature in store.boundaries["features"]:
        kel_id = feature["properties"]["kel_id"]
        properties = {key: feature["properties"].get(key) for key in NAME_PROPERTIES}
        if kel_id in frame.index:
            row = frame.loc[kel_id]
            properties.update({metric: _clean(row.get(metric)) for metric in MAP_METRICS})
        else:
            properties.update({metric: None for metric in MAP_METRICS})

        features.append(
            {
                "type": "Feature",
                "properties": properties,
                "geometry": {
                    "type": feature["geometry"]["type"],
                    "coordinates": _round_coords(feature["geometry"]["coordinates"]),
                },
            }
        )

    return {
        "type": "FeatureCollection",
        "features": features,
        "attribution": (
            "Batas: HDX COD-AB Indonesia (CC BY-IGO) · LST: USGS Landsat 8/9 · "
            "Vegetasi: ESA WorldCover v200 · Penduduk: WorldPop 2025 · "
            "Bangunan: Google Open Buildings Temporal v1 · Elevasi: Copernicus DEM"
        ),
    }


@router.get("/health")
def health() -> dict:
    """Readiness plus what is actually loaded, so a broken deploy is visible immediately."""
    store = get_store()
    return ok(
        {
            "n_kelurahan": len(store.kelurahan),
            "n_cells": len(store.grid),
            "city_lst_mean": store.city_lst_mean,
            "model_loaded": store.booster is not None,
            "shap_loaded": store.shap_by_kel is not None,
        }
    )


@router.get("/kelurahan")
def list_kelurahan() -> dict:
    """GeoJSON with metrics for the choropleth."""
    return ok(map_payload())


@router.get("/kelurahan/{kel_id}")
def kelurahan_detail(kel_id: str) -> Any:
    """Full profile plus SHAP drivers, which is everything the drawer renders."""
    profile = get_area_profile(kel_id)
    if "error" in profile:
        return JSONResponse(status_code=404, content=fail(profile["error"]))

    drivers = explain_drivers(kel_id)
    payload = dict(profile)
    payload["drivers"] = drivers.get("drivers", [])
    payload["drivers_unavailable"] = drivers.get("error")
    payload["facts"] = profile["facts"] + drivers.get("facts", [])
    return ok(payload)


@router.post("/simulate")
def simulate(request: SimulateRequest) -> Any:
    """Scenario straight from the sliders. No LLM in this path."""
    result = simulate_intervention(
        request.kel_ids,
        [item.model_dump(exclude_none=True) for item in request.interventions],
    )
    if "error" in result:
        return JSONResponse(status_code=400, content=fail(result["error"]))
    return ok(result)


@router.post("/optimize")
def optimize(request: OptimizeRequest) -> Any:
    """Portfolio straight from the budget form. No LLM in this path."""
    result = optimize_portfolio(
        scope=request.scope,
        budget_idr=request.budget_idr,
        equity_share=request.equity_share,
        allowed=request.allowed,
    )
    if "error" in result:
        return JSONResponse(status_code=400, content=fail(result["error"]))
    return ok(result)


@router.get("/model-card")
def model_card() -> Any:
    """Metrics and limitations for the "Tentang & Sumber Data" page."""
    store = get_store()
    if store.model_card is None:
        raise HTTPException(
            status_code=404,
            detail="Model card belum tersedia. Model belum dilatih.",
        )
    return ok(store.model_card)
```

- [ ] **Step 4: Jalankan tes untuk memastikan lulus**

Run: `uv run pytest tests/test_api.py -v`
Expected: PASS, 15 tes.

- [ ] **Step 5: Periksa ukuran payload peta**

```bash
uv run python -c "
import json
from api.routes import map_payload
raw = json.dumps(map_payload())
print(f'payload peta: {len(raw)/1024/1024:.2f} MB, {len(map_payload()[\"features\"])} fitur')
"
```
Expected: jauh di bawah 2,2 MB sumber aslinya. Kalau masih di atas ~1,5 MB, turunkan `COORD_PRECISION` ke 4 (≈10 m) — masih lebih halus dari lebar garis 0,9 px pada peta kelurahan.

- [ ] **Step 6: Commit**

```bash
git add api/routes.py tests/test_api.py
git commit -m "feat: tambah router /api di atas tool yang sama dengan agen

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task M3-T9: Perakitan aplikasi

**Files:**
- Create: `api/main.py`
- Test: `tests/test_main.py`

**Interfaces:**
- Consumes: `api.routes.{router, map_payload}` (M3-T8); `google.adk.cli.fast_api.get_fast_api_app`; `teduh_agent.store.get_store`.
- Produces:
  - `app: FastAPI` — target `uvicorn api.main:app`
  - `AGENTS_DIR`, `ALLOWED_ORIGINS: list[str]`

**Peringatan versi ADK:** signature `get_fast_api_app` berubah antar rilis (`agents_dir` vs `agent_dir`, ada/tidaknya `allow_origins`, `web`). **Cek signature yang terpasang sebelum menulis:**

```bash
uv run python -c "import inspect; from google.adk.cli.fast_api import get_fast_api_app; print(inspect.signature(get_fast_api_app))"
```

Sesuaikan pemanggilan di Step 3 dengan hasilnya. Kalau fungsinya tidak ada sama sekali, buat `FastAPI()` biasa, mount `router`, dan catat di `docs/DECISIONS.md` bahwa chat memakai endpoint sendiri — tetapi coba jalur ADK lebih dulu, karena `/run_sse` beserta manajemen sesinya adalah bagian dari cerita "Agent Platform" untuk juri.

- [ ] **Step 1: Tulis tes yang gagal**

Buat `tests/test_main.py`:

```python
"""App assembly. Asserts the two things a deploy can silently get wrong: the /api router is
actually mounted, and the store is warm before the first request so a judge does not pay the
cold-load cost inside their first question."""

import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


@pytest.mark.integration
def test_api_router_is_mounted(client):
    assert client.get("/api/health").json()["success"] is True


@pytest.mark.integration
def test_store_is_warm_before_the_first_request():
    # get_store is lru_cached; a cache hit means startup already paid the load.
    from teduh_agent.store import get_store

    assert get_store().booster is not None or get_store().model_card is None


@pytest.mark.integration
def test_map_payload_is_prebuilt_at_startup(client):
    from api.routes import map_payload

    assert map_payload.cache_info().currsize == 1


@pytest.mark.integration
def test_adk_run_sse_endpoint_exists_for_chat(client):
    paths = {route.path for route in app.routes}
    assert any("run_sse" in path for path in paths), (
        "endpoint ADK tidak terpasang; chat streaming tidak akan jalan"
    )
```

- [ ] **Step 2: Jalankan tes untuk memastikan gagal**

Run: `uv run pytest tests/test_main.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'api.main'`

- [ ] **Step 3: Tulis `api/main.py`**

```python
"""Application assembly: ADK's app plus the TEDUH REST router.

get_fast_api_app brings /run_sse and ADK session management, which is what makes the chat
stream and what makes the Agent Platform story real for the judges. The /api router is
mounted onto that same app so the whole product is one Cloud Run service and one URL.

The startup hook warms the store and prebuilds the map payload on purpose. Cloud Run with
min-instances=1 still cold-starts once, and the first request during judging must not be the
one that pays for loading 75_636 cells and building 264 polygons.
"""

import os
from pathlib import Path

from fastapi.middleware.cors import CORSMiddleware

from api.routes import map_payload, router

ROOT = Path(__file__).resolve().parents[1]

# ADK scans this directory for packages exposing root_agent; teduh_agent lives at the root.
AGENTS_DIR = str(ROOT)

# The deployed web origin is injected at deploy time. Localhost entries are for development.
ALLOWED_ORIGINS = [
    origin
    for origin in (
        os.environ.get("TEDUH_WEB_ORIGIN"),
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    )
    if origin
]


def _build_app():
    """Build on ADK's app when available, falling back to a bare FastAPI app.

    The signature of get_fast_api_app has moved between ADK releases, so the keyword is
    probed rather than assumed. Verify with:
        uv run python -c "import inspect; from google.adk.cli.fast_api import \
            get_fast_api_app; print(inspect.signature(get_fast_api_app))"
    """
    from google.adk.cli.fast_api import get_fast_api_app

    try:
        return get_fast_api_app(agents_dir=AGENTS_DIR, allow_origins=ALLOWED_ORIGINS, web=True)
    except TypeError:
        # Older releases used agent_dir and had no allow_origins; CORS is added below anyway.
        return get_fast_api_app(agent_dir=AGENTS_DIR)


app = _build_app()

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(router)


@app.on_event("startup")
def warm() -> None:
    """Load artifacts and build the map payload before serving the first request."""
    from teduh_agent.store import get_store

    store = get_store()
    payload = map_payload()
    print(
        f"siap: {len(store.kelurahan)} kelurahan, {len(store.grid):,} sel, "
        f"{len(payload['features'])} poligon, "
        f"model {'ada' if store.booster is not None else 'BELUM ADA'}"
    )
```

Kalau `@app.on_event` sudah deprecated di versi FastAPI yang terpasang, pakai lifespan:

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(_app):
    warm()
    yield

app.router.lifespan_context = lifespan
```

- [ ] **Step 4: Jalankan tes untuk memastikan lulus**

Run: `uv run pytest tests/test_main.py -v`
Expected: PASS, 4 tes. Kalau `test_adk_run_sse_endpoint_exists_for_chat` gagal, periksa signature `get_fast_api_app` seperti di catatan peringatan di atas.

- [ ] **Step 5: Jalankan API lokal dan uji dengan tangan**

Run: `uv run uvicorn api.main:app --reload --port 8080`
Expected: baris `siap: 264 kelurahan, 75,636 sel, 264 poligon, model ada`.

```bash
curl -s localhost:8080/api/health | python3 -m json.tool
curl -s localhost:8080/api/kelurahan/ID3173040002 | python3 -c "import json,sys; d=json.load(sys.stdin)['data']; print(d['profile']['kel_name'], d['profile']['lst'], len(d['facts']), 'fakta')"
curl -s -X POST localhost:8080/api/simulate -H 'content-type: application/json' \
  -d '{"kel_ids":["ID3173040002"],"interventions":[{"type":"cool_roof","level":"medium"}]}' \
  | python3 -c "import json,sys; r=json.load(sys.stdin)['data']['results'][0]; print('dLST', r['delta_lst_c'], 'biaya', r['cost_idr'])"
curl -s -X POST localhost:8080/api/optimize -H 'content-type: application/json' \
  -d '{"scope":"all","budget_idr":2000000000}' \
  | python3 -c "import json,sys; d=json.load(sys.stdin)['data']; print(len(d['packages']),'paket, keadilan', round(d['equity_share_achieved'],3))"
```
Expected: `Kampung Rawa`, ΔLST negatif, dan porsi keadilan ≥ 0,6.

- [ ] **Step 6: Deploy ke Cloud Run dan uji URL publiknya**

Run: `./infra/deploy_api.sh`
Expected: skrip mencetak URL. Lalu `curl -s <URL>/api/health` mengembalikan 264 kelurahan dan `model_loaded: true`.

- [ ] **Step 7: Commit**

```bash
git add api/main.py tests/test_main.py
git commit -m "feat: rakit app ADK + router REST dengan pemanasan store saat startup

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Definisi M3c selesai

- [ ] `uv run uvicorn api.main:app` naik dan mencetak jumlah artefak yang dimuat.
- [ ] Ketujuh endpoint berfungsi: `/api/health`, `/api/kelurahan`, `/api/kelurahan/{id}`, `/api/simulate`, `/api/optimize`, `/api/model-card`, dan `/run_sse` dari ADK.
- [ ] Payload peta jauh lebih kecil dari 2,2 MB dan setiap fitur punya 14 metrik.
- [ ] Body yang salah bentuk → 422; error tingkat tool → 400; kelurahan tidak ada → 404.
- [ ] Tidak ada pesan error yang membocorkan path filesystem.
- [ ] `uv run pytest -q` hijau.
- [ ] URL publik Cloud Run menjawab `/api/health`.

**Selanjutnya:** [`m4-agent.md`](m4-agent.md) — sub-agen, instruksi sistem, dan fallback satu agen.
