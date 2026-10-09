# M3b — Tool Deterministik Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> Baca `docs/superpowers/plans/README.md` bagian **Global Constraints** dan **Interface Registry** sebelum mulai. Prasyarat: **M0, M2, M3a selesai**.

**Goal:** Tujuh tool Python deterministik yang menjadi satu-satunya jalan angka boleh sampai ke Gemini, masing-masing mengembalikan `facts` dengan sumber.

**Architecture:** Tool adalah pembungkus tipis di atas `model/`. Tidak ada aritmetika baru di lapisan ini — kalau sebuah tool perlu menghitung sesuatu yang belum ada di `model/`, fungsinya ditambahkan di `model/`, bukan di sini. Semua tool menerima `tool_context` opsional supaya `api/routes.py` bisa memanggil fungsi yang sama tanpa sesi ADK.

**Tech Stack:** google-adk (`ToolContext`), pandas, OR-Tools CP-SAT, difflib.

## Global Constraints

- **Nama fungsi tool tidak boleh diubah.** `tests/eval/golden_questions.yaml` mencocokkannya: `find_area`, `get_area_profile`, `rank_priority_areas`, `explain_drivers`, `simulate_intervention`, `optimize_portfolio`, `get_evidence`.
- **Setiap tool mengembalikan `dict` dengan kunci `facts: list[Fact]`** (CLAUDE.md aturan 2). Angka apa pun yang muncul di payload juga harus ada sebagai `Fact`.
- Tool boleh mengembalikan `map_highlight: list[str]` berisi `kel_id` untuk menyorot peta.
- **Docstring tool ditulis Bahasa Indonesia** karena ADK mengirimkannya ke Gemini sebagai deskripsi tool dan pengguna bertanya dalam Bahasa Indonesia. Komentar `#` dan identifier tetap Inggris.
- **Jangan mengarang angka.** Kalau data tidak ada, kembalikan `{"error": "...", "facts": []}` — jangan menebak.
- ΔLST selalu diberi label indikatif dan suhu **permukaan**.
- `tests/test_optimize.py` adalah tes **wajib** (CLAUDE.md): total biaya ≤ anggaran, kendala porsi keadilan terpenuhi.
- Commit conventional, diakhiri `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`.

### Catatan data penting

`kelurahan_metrics.parquet` **tidak punya** `kec_name` dan `kota_name` — keduanya hanya ada di properti `data/boundaries/kelurahan.geojson`. `find_area` harus menggabungkan keduanya, kalau tidak pencarian "Jakarta Timur" atau "Pademangan" tidak akan pernah cocok.

Kode kota: `ID3171` Jakarta Selatan · `ID3172` Jakarta Timur · `ID3173` Jakarta Pusat · `ID3174` Jakarta Barat · `ID3175` Jakarta Utara.

### Konvensi id Fact (dipakai penanda `[[F:id]]` di brief M5)

| Pola | Contoh |
|---|---|
| `kel_<kel_id>.<metrik>` | `kel_ID3173040002.lst` |
| `rank.<scope>.<i>.<metrik>` | `rank.ID3172.1.hvi` |
| `driver.<kel_id>.<feature>` | `driver.ID3173040002.tree_frac` |
| `sim.<kel_id>.<metrik>` | `sim.ID3173040002.delta_lst` |
| `opt.<metrik>` | `opt.total_cost` |
| `evidence.<ev_id>.<batas>` | `evidence.ev_ndvi_kl_2025.min` |

---

## File Structure

| File | Tanggung jawab |
|---|---|
| `teduh_agent/tools/__init__.py` | Penanda paket + daftar `ALL_TOOLS` yang dipakai M4. |
| `teduh_agent/tools/areas.py` | Pencarian wilayah, profil, peringkat, faktor pendorong. |
| `teduh_agent/tools/scenario_tools.py` | `simulate_intervention` + pembanding literatur. |
| `teduh_agent/tools/optimize.py` | `optimize_portfolio` dengan CP-SAT, anggaran + kendala keadilan. |
| `teduh_agent/tools/evidence.py` | `get_evidence` dengan sitasi. |

---

## Task M3-T3: Tool wilayah

**Files:**
- Create: `teduh_agent/tools/__init__.py`
- Create: `teduh_agent/tools/areas.py`
- Test: `tests/test_areas.py`

**Interfaces:**
- Consumes: `teduh_agent.store.get_store` (M0-T3); `teduh_agent.facts.{fact, record, SOURCE_DATA, SOURCE_MODEL}` (M0-T2); `model.hvi.{components, hvi, load_weights, rank}` (M2-T1); `model.explain.top_drivers` (M2-T3).
- Produces:
  - `SCOPE_ALL = "all"`, `DEFAULT_TOP_K = 10`, `MAX_TOP_K = 50`, `FUZZY_CUTOFF = 0.6`
  - `FEATURE_LABELS: dict[str, str]` — nama fitur model → label Bahasa Indonesia untuk UI
  - `directory() -> pd.DataFrame` — `lru_cache(1)`, metrics digabung `kec_name` + `kota_name`
  - `find_area(query: str, tool_context: ToolContext | None = None) -> dict`
  - `get_area_profile(kel_id: str, tool_context: ToolContext | None = None) -> dict`
  - `rank_priority_areas(scope: str = SCOPE_ALL, top_k: int = DEFAULT_TOP_K, weights: dict | None = None, tool_context: ToolContext | None = None) -> dict`
  - `explain_drivers(kel_id: str, tool_context: ToolContext | None = None) -> dict`

- [ ] **Step 1: Tulis tes yang gagal**

Buat `tests/test_areas.py`:

```python
"""These four tools answer nine of the twenty golden questions, so their names and their
facts contract are load-bearing. The fuzzy-search tests matter more than they look: a planner
types "Jakarta Timur", and kota_name lives only in the GeoJSON, not in the metrics parquet."""

import pytest

from teduh_agent.facts import SOURCE_DATA
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

    monkeypatch.setattr(areas_module, "get_store", lambda: _StoreWithoutShap())
    result = explain_drivers("ID3173040002")
    assert "error" in result
    assert result["facts"] == []


class _StoreWithoutShap:
    shap_by_kel = None
    booster = None

    def __init__(self) -> None:
        from teduh_agent.store import load

        self._real = load()

    def __getattr__(self, name):
        return getattr(self._real, name)
```

Catatan: tes terakhir memakai kelas pembantu di akhir file; letakkan `_StoreWithoutShap` **sebelum** fungsi yang memakainya kalau linter mengeluh, atau pakai `pytest.MonkeyPatch` dengan `types.SimpleNamespace` yang menyalin atribut store nyata.

- [ ] **Step 2: Jalankan tes untuk memastikan gagal**

Run: `uv run pytest tests/test_areas.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'teduh_agent.tools'`

- [ ] **Step 3: Tulis `teduh_agent/tools/__init__.py`**

```python
"""Deterministic tools. This is the only path by which a number reaches Gemini.

Each tool is a thin wrapper over model/: it fetches, formats, and attaches provenance, but
performs no arithmetic of its own. If a tool needs a calculation that model/ does not
provide, the function belongs in model/, not here -- that boundary is what makes CLAUDE.md
rule 1 auditable.

Every tool takes an optional tool_context so api/routes.py can call the same function over
HTTP with no ADK session in play.
"""
```

`ALL_TOOLS` ditambahkan di M4 setelah semua tool ada, agar `__init__.py` tidak mengimpor modul yang belum dibuat.

- [ ] **Step 4: Tulis `teduh_agent/tools/areas.py`**

```python
"""Area lookup, profile, ranking, and SHAP drivers.

find_area joins kelurahan_metrics.parquet with the GeoJSON properties because kec_name and
kota_name exist ONLY in the boundary file. Without that join, "Jakarta Timur" -- the single
most likely thing a planner types -- matches nothing at all.

rank_priority_areas recomputes HVI from model/hvi.py when the caller supplies weights,
rather than reading the baked hvi column. The weights are a policy choice the UI exposes, and
a stale column would make the ranking disagree with the map.
"""

import difflib
import re
from functools import lru_cache

import pandas as pd
from google.adk.tools import ToolContext

from model.explain import top_drivers
from model.hvi import DEFAULT_WEIGHTS, components, hvi, load_weights, rank
from teduh_agent.facts import SOURCE_DATA, SOURCE_MODEL, fact, record
from teduh_agent.store import get_store

SCOPE_ALL = "all"
DEFAULT_TOP_K = 10
MAX_TOP_K = 50

# difflib ratio below which a near-miss is not a match at all.
FUZZY_CUTOFF = 0.6

# Administrative prefixes a user types but the data does not store.
PREFIX_PATTERN = re.compile(r"^(kel\.?|kelurahan|kec\.?|kecamatan|kota|kab\.?|kabupaten)\s+")

# Model feature names are English; these are what the UI and the agent must say instead.
FEATURE_LABELS: dict[str, str] = {
    "albedo": "Albedo permukaan (daya pantul)",
    "ndvi": "Kerapatan vegetasi (NDVI)",
    "ndbi": "Indeks lahan terbangun (NDBI)",
    "ndwi": "Indeks kebasahan (NDWI)",
    "tree_frac": "Tutupan pohon",
    "built_frac": "Fraksi lahan terbangun",
    "water_frac": "Fraksi badan air",
    "roof_frac": "Fraksi atap bangunan",
    "bldg_h_mean": "Tinggi bangunan rata-rata",
    "elev_m": "Elevasi",
    "dist_coast_km": "Jarak ke pantai",
    "pop": "Kepadatan penduduk",
}


def _normalise(text: str) -> str:
    return PREFIX_PATTERN.sub("", text.strip().lower())


@lru_cache(maxsize=1)
def directory() -> pd.DataFrame:
    """Kelurahan metrics plus the two names that live only in the boundary file."""
    store = get_store()
    properties = pd.DataFrame(
        [feature["properties"] for feature in store.boundaries["features"]]
    ).set_index("kel_id")
    return store.kelurahan.join(properties[["kec_name", "kota_name"]], how="left")


def _rows_to_matches(frame: pd.DataFrame) -> list[dict]:
    return [
        {
            "kel_id": kel_id,
            "kel_name": row["kel_name"],
            "kec_id": row["kec_id"],
            "kec_name": row["kec_name"],
            "kota_id": row["kota_id"],
            "kota_name": row["kota_name"],
        }
        for kel_id, row in frame.iterrows()
    ]


def _match_by_column(frame: pd.DataFrame, column: str, query: str) -> pd.DataFrame:
    normalised = frame[column].fillna("").str.lower().map(_normalise)
    exact = frame[normalised == query]
    if not exact.empty:
        return exact
    contains = frame[normalised.str.contains(re.escape(query), regex=True)]
    if not contains.empty:
        return contains
    close = difflib.get_close_matches(query, normalised.unique().tolist(), n=1,
                                      cutoff=FUZZY_CUTOFF)
    return frame[normalised == close[0]] if close else frame.iloc[0:0]


def find_area(query: str, tool_context: ToolContext | None = None) -> dict:
    """Cari wilayah berdasarkan nama kelurahan, kecamatan, atau kota di DKI Jakarta.

    Pencocokan longgar, jadi salah ketik kecil masih ketemu. Gunakan tool ini lebih dulu
    setiap kali pengguna menyebut nama tempat, untuk mendapatkan kel_id yang dibutuhkan
    tool lain.

    Args:
        query: nama tempat yang disebut pengguna, misalnya "Kampung Rawa", "Pademangan",
            atau "Jakarta Timur".

    Returns:
        dict dengan `matches` (daftar wilayah beserta kel_id), `scope_type`
        ("kelurahan", "kecamatan", atau "kota"), `scope_id`, dan `facts`.
    """
    normalised = _normalise(query)
    if not normalised:
        return {"error": "Nama wilayah kosong.", "matches": [], "facts": []}

    frame = directory()
    for column, scope_type in (
        ("kel_name", "kelurahan"),
        ("kec_name", "kecamatan"),
        ("kota_name", "kota"),
    ):
        hit = _match_by_column(frame, column, normalised)
        if hit.empty:
            continue
        scope_id = (
            hit.index[0]
            if scope_type == "kelurahan"
            else hit.iloc[0]["kec_id" if scope_type == "kecamatan" else "kota_id"]
        )
        facts = [
            fact(
                f"find.{normalised}.count",
                f"Jumlah wilayah cocok untuk {query!r}",
                len(hit),
                "wilayah",
                SOURCE_DATA,
            )
        ]
        record(tool_context, facts)
        return {
            "matches": _rows_to_matches(hit),
            "scope_type": scope_type,
            "scope_id": str(scope_id),
            "facts": facts,
        }

    return {
        "error": (
            f"Tidak ada wilayah bernama {query!r} di data TEDUH. "
            "Cakupan saat ini hanya DKI Jakarta daratan."
        ),
        "matches": [],
        "facts": [],
    }


def get_area_profile(kel_id: str, tool_context: ToolContext | None = None) -> dict:
    """Ambil profil panas dan kerentanan satu kelurahan.

    Berisi suhu permukaan rata-rata, selisihnya dari rata-rata kota, peringkat HVI,
    keempat komponen HVI, vegetasi, tutupan lahan, jumlah penduduk, dan jumlah warga
    rentan. Pakai find_area lebih dulu untuk mendapatkan kel_id.

    Args:
        kel_id: kode kelurahan 12 karakter, misalnya "ID3173040002".

    Returns:
        dict dengan `profile`, `total_kelurahan`, `map_highlight`, dan `facts`.
    """
    frame = directory()
    if kel_id not in frame.index:
        return {"error": f"Kelurahan {kel_id!r} tidak ada di data TEDUH.", "facts": []}

    store = get_store()
    row = frame.loc[kel_id]
    anomaly = float(row["lst_c_mean"]) - store.city_lst_mean
    vulnerable = float(row["pop_u5"]) + float(row["pop_65p"])

    prefix = f"kel_{kel_id}"
    numeric: list[tuple[str, str, float, str]] = [
        ("lst", "Suhu permukaan rata-rata", float(row["lst_c_mean"]), "degC"),
        ("lst_anomaly", "Selisih suhu permukaan dari rata-rata kota", anomaly, "degC"),
        ("hvi", "Indeks Kerentanan Panas (HVI)", float(row["hvi"]), ""),
        ("hvi_rank", "Peringkat HVI", int(row["hvi_rank"]), "peringkat"),
        ("ndvi", "Kerapatan vegetasi (NDVI)", float(row["ndvi_mean"]), ""),
        ("tree_frac", "Tutupan pohon", float(row["tree_frac_mean"]), "fraksi"),
        ("built_frac", "Fraksi lahan terbangun", float(row["built_frac_mean"]), "fraksi"),
        ("water_frac", "Fraksi badan air", float(row["water_frac_mean"]), "fraksi"),
        ("pop", "Jumlah penduduk", float(row["pop"]), "jiwa"),
        ("vulnerable", "Warga rentan (balita dan lansia)", vulnerable, "jiwa"),
        (
            "exposed_vulnerable",
            "Warga rentan di sel paling panas",
            float(row["exposed_vulnerable"]),
            "jiwa",
        ),
        ("H", "Komponen HVI: bahaya panas", float(row["H"]), ""),
        ("E", "Komponen HVI: keterpaparan", float(row["E"]), ""),
        ("S", "Komponen HVI: kepekaan", float(row["S"]), ""),
        ("A", "Komponen HVI: kurangnya kapasitas adaptif", float(row["A"]), ""),
    ]

    facts = [
        fact(f"{prefix}.{key}", label, value, unit, SOURCE_DATA)
        for key, label, value, unit in numeric
    ]
    facts.append(
        fact(
            "data.city_lst_mean",
            "Suhu permukaan rata-rata DKI Jakarta",
            store.city_lst_mean,
            "degC",
            SOURCE_DATA,
        )
    )
    record(tool_context, facts)

    return {
        "profile": {
            "kel_id": kel_id,
            "kel_name": row["kel_name"],
            "kec_name": row["kec_name"],
            "kota_name": row["kota_name"],
            **{key: value for key, _, value, _ in numeric},
        },
        "total_kelurahan": len(frame),
        "note": "Suhu permukaan (LST) dari Landsat 8/9, bukan suhu udara.",
        "map_highlight": [kel_id],
        "facts": facts,
    }


def _resolve_scope(frame: pd.DataFrame, scope: str) -> tuple[pd.DataFrame, str] | None:
    """Narrow the directory to a scope given either a code or a name."""
    if not scope or scope.lower() == SCOPE_ALL:
        return frame, SCOPE_ALL
    if scope in frame["kota_id"].values:
        return frame[frame["kota_id"] == scope], scope
    if scope in frame["kec_id"].values:
        return frame[frame["kec_id"] == scope], scope

    located = find_area(scope)
    if not located["matches"]:
        return None
    ids = [match["kel_id"] for match in located["matches"]]
    return frame.loc[ids], located["scope_id"]


def rank_priority_areas(
    scope: str = SCOPE_ALL,
    top_k: int = DEFAULT_TOP_K,
    weights: dict | None = None,
    tool_context: ToolContext | None = None,
) -> dict:
    """Urutkan kelurahan dari yang paling rentan terhadap panas (HVI tertinggi).

    Pakai tool ini untuk pertanyaan tentang prioritas, kelurahan terpanas, atau wilayah
    mana yang perlu ditangani lebih dulu. Bobot HVI bisa diubah kalau pengguna ingin
    menekankan aspek tertentu.

    Args:
        scope: "all" untuk seluruh DKI, atau nama/kode kota atau kecamatan.
        top_k: banyak kelurahan yang dikembalikan, maksimal 50.
        weights: opsional, bobot HVI {"wE": ..., "wS": ..., "wA": ...} yang harus
            berjumlah 1. Kalau kosong, memakai bobot default 0,4 / 0,3 / 0,3.

    Returns:
        dict dengan `areas` (urut peringkat), `weights` yang dipakai, `scope_id`,
        `map_highlight`, dan `facts`.
    """
    frame = directory()
    resolved = _resolve_scope(frame, scope)
    if resolved is None:
        return {
            "error": f"Wilayah {scope!r} tidak ada di data TEDUH (hanya DKI Jakarta).",
            "facts": [],
        }
    scoped, scope_id = resolved
    limit = max(1, min(int(top_k), MAX_TOP_K))

    store = get_store()
    active = load_weights(store.hvi_cfg) if weights is None else dict(weights)
    try:
        scores = hvi(components(scoped), active)
    except (KeyError, ValueError) as error:
        return {"error": f"Bobot HVI tidak valid: {error}", "facts": []}

    ranked = scoped.assign(hvi_scoped=scores, rank_scoped=rank(scores))
    ranked = ranked.nsmallest(limit, "rank_scoped")

    areas: list[dict] = []
    facts = []
    for position, (kel_id, row) in enumerate(ranked.iterrows(), start=1):
        areas.append(
            {
                "rank": position,
                "kel_id": kel_id,
                "kel_name": row["kel_name"],
                "kec_name": row["kec_name"],
                "kota_id": row["kota_id"],
                "kota_name": row["kota_name"],
                "hvi": float(row["hvi_scoped"]),
                "lst_c_mean": float(row["lst_c_mean"]),
                "tree_frac": float(row["tree_frac_mean"]),
                "exposed_vulnerable": float(row["exposed_vulnerable"]),
            }
        )
        label = f"HVI {row['kel_name']} (peringkat {position})"
        facts.append(
            fact(
                f"rank.{scope_id}.{position}.hvi",
                label,
                float(row["hvi_scoped"]),
                "",
                SOURCE_DATA,
            )
        )

    for key, value in active.items():
        facts.append(
            fact(f"rank.{scope_id}.weight.{key}", f"Bobot HVI {key}", float(value), "",
                 SOURCE_DATA)
        )
    record(tool_context, facts)

    return {
        "areas": areas,
        "weights": active,
        "scope_id": scope_id,
        "n_in_scope": len(scoped),
        "map_highlight": [area["kel_id"] for area in areas],
        "facts": facts,
    }


def explain_drivers(kel_id: str, tool_context: ToolContext | None = None) -> dict:
    """Jelaskan faktor apa yang membuat satu kelurahan panas, menurut model (SHAP).

    Mengembalikan tiga sampai lima faktor terbesar beserta besarnya kontribusi dalam
    derajat Celsius dan arahnya (memanaskan atau mendinginkan). Pakai tool ini kalau
    pengguna bertanya KENAPA sebuah wilayah panas, bukan hanya seberapa panas.

    Args:
        kel_id: kode kelurahan 12 karakter, misalnya "ID3173040002".

    Returns:
        dict dengan `drivers`, `pred_lst_c`, `map_highlight`, dan `facts`.
    """
    store = get_store()
    if store.shap_by_kel is None:
        return {
            "error": (
                "Penjelasan faktor pendorong belum tersedia karena artefak SHAP belum "
                "dibuat. Jalankan model.explain lebih dulu."
            ),
            "facts": [],
        }

    table = store.shap_by_kel.set_index("kel_id")
    if kel_id not in table.index:
        return {"error": f"Kelurahan {kel_id!r} tidak ada di tabel SHAP.", "facts": []}

    row = table.loc[kel_id]
    drivers = [
        {**driver, "label": FEATURE_LABELS.get(driver["feature"], driver["feature"])}
        for driver in top_drivers(row)
    ]

    facts = [
        fact(
            f"driver.{kel_id}.{driver['feature']}",
            f"Kontribusi {driver['label']} terhadap suhu permukaan",
            driver["contribution_c"],
            "degC",
            SOURCE_MODEL,
        )
        for driver in drivers
    ]
    facts.append(
        fact(
            f"kel_{kel_id}.pred_lst",
            "Suhu permukaan hasil prediksi model",
            float(row["pred_lst_c"]),
            "degC",
            SOURCE_MODEL,
        )
    )
    record(tool_context, facts)

    return {
        "drivers": drivers,
        "pred_lst_c": float(row["pred_lst_c"]),
        "note": (
            "Kontribusi dari model LightGBM (SHAP) dan bersifat korelasional, "
            "bukan sebab-akibat."
        ),
        "map_highlight": [kel_id],
        "facts": facts,
    }
```

- [ ] **Step 5: Jalankan tes untuk memastikan lulus**

Run: `uv run pytest tests/test_areas.py -v`
Expected: PASS. Tes `explain_drivers` di-skip kalau `shap_by_kel.parquet` belum ada.

- [ ] **Step 6: Coba lewat agen**

Tambahkan sementara keempat tool ke `root_agent.tools` di `teduh_agent/agent.py`, lalu:

Run: `uv run adk web`
Tanya: "Kelurahan mana di Jakarta Timur yang paling perlu diprioritaskan?"
Expected: `find_area` lalu `rank_priority_areas` terpanggil, dan jawabannya menyebut kelurahan nyata dengan HVI dari fakta.

- [ ] **Step 7: Commit**

```bash
git add teduh_agent/tools/__init__.py teduh_agent/tools/areas.py tests/test_areas.py
git commit -m "feat: tambah tool wilayah, profil, peringkat, dan faktor pendorong

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task M3-T4: Tool simulasi skenario

**Files:**
- Create: `teduh_agent/tools/scenario_tools.py`
- Test: `tests/test_scenario_tools.py`

**Interfaces:**
- Consumes: `model.scenario.{Intervention, LEVELS, PARAM_NAME, INTERVENTION_TYPES, from_level, simulate, training_quantiles}` (M3-T1); `model.train.prepare` (M2-T2); `teduh_agent.tools.evidence.evidence_for` (M3-T6); `teduh_agent.store.get_store`; `teduh_agent.facts`.
- Produces:
  - `simulate_intervention(kel_ids: list[str], interventions: list[dict], tool_context: ToolContext | None = None) -> dict`
  - `training_frame() -> pd.DataFrame` — `lru_cache(1)`, grid siap-model
  - `quantiles() -> pd.Series` — `lru_cache(1)`

`interventions` berupa daftar dict agar ADK bisa melewatkannya sebagai JSON: `{"type": "cool_roof", "level": "medium"}` atau `{"type": "tree_planting", "params": {"canopy_increase_pp": 7.5}}`.

- [ ] **Step 1: Tulis tes yang gagal**

Buat `tests/test_scenario_tools.py`:

```python
"""The tool layer over model/scenario.py. Two things are checked here that the engine tests
cannot: that the agent-facing JSON shape is accepted, and that every scenario answer carries
the literature comparison CONCEPT §7.5 requires -- a model number with no published range
beside it is exactly the overclaiming this product is designed to avoid."""

import pytest

from teduh_agent.tools.scenario_tools import simulate_intervention


class FakeToolContext:
    def __init__(self) -> None:
        self.state: dict = {}


@pytest.mark.integration
def test_accepts_an_intervention_given_by_level():
    result = simulate_intervention(["ID3173040002"], [{"type": "cool_roof", "level": "medium"}])
    assert result["results"][0]["kel_id"] == "ID3173040002"


@pytest.mark.integration
def test_accepts_an_intervention_given_by_explicit_params():
    result = simulate_intervention(
        ["ID3173040002"],
        [{"type": "tree_planting", "params": {"canopy_increase_pp": 7.5}}],
    )
    assert result["results"][0]["delta_lst_c"] <= 1e-9


@pytest.mark.integration
def test_simulates_several_kelurahan_in_one_call():
    result = simulate_intervention(
        ["ID3173040002", "ID3172030001"], [{"type": "cool_roof", "level": "low"}]
    )
    assert {row["kel_id"] for row in result["results"]} == {"ID3173040002", "ID3172030001"}


@pytest.mark.integration
def test_every_result_carries_the_indicative_caveat():
    result = simulate_intervention(["ID3173040002"], [{"type": "cool_roof", "level": "low"}])
    assert "indikatif" in result["note"].lower()
    assert "permukaan" in result["note"].lower()


@pytest.mark.integration
def test_every_result_carries_a_literature_comparison():
    # CONCEPT §7.5: the model number is always shown next to a published range.
    result = simulate_intervention(["ID3173040002"], [{"type": "cool_roof", "level": "medium"}])
    assert result["evidence"], "hasil skenario tanpa pembanding literatur"
    assert all(entry["url_or_doi"] for entry in result["evidence"])


@pytest.mark.integration
def test_emits_a_fact_for_each_reported_number():
    result = simulate_intervention(["ID3173040002"], [{"type": "cool_roof", "level": "medium"}])
    ids = {f["id"] for f in result["facts"]}
    assert "sim.ID3173040002.delta_lst" in ids
    assert "sim.ID3173040002.cost" in ids
    assert "sim.ID3173040002.area" in ids
    assert "sim.ID3173040002.vulnerable_benefiting" in ids


@pytest.mark.integration
def test_cost_facts_cite_their_price_source():
    result = simulate_intervention(["ID3173040002"], [{"type": "tree_planting",
                                                       "level": "low"}])
    cost_facts = [f for f in result["facts"] if f["id"].endswith(".cost")]
    assert cost_facts
    for entry in cost_facts:
        assert entry["source"].startswith("assumption:") or "Kepgub" in entry["source"]


@pytest.mark.integration
def test_extrapolation_is_surfaced_in_the_payload():
    result = simulate_intervention(["ID3173040002"], [{"type": "cool_roof", "level": "high"}])
    assert "extrapolation" in result["results"][0]


@pytest.mark.integration
def test_records_facts_into_the_session_ledger():
    ctx = FakeToolContext()
    simulate_intervention(["ID3173040002"], [{"type": "cool_roof", "level": "low"}], ctx)
    assert ctx.state["facts"]


@pytest.mark.integration
def test_rejects_an_unknown_kelurahan_without_guessing():
    result = simulate_intervention(["ID9999999999"], [{"type": "cool_roof", "level": "low"}])
    assert "error" in result
    assert result["facts"] == []


@pytest.mark.integration
def test_rejects_an_unknown_intervention_type():
    result = simulate_intervention(["ID3173040002"], [{"type": "cool_pavement",
                                                       "level": "low"}])
    assert "error" in result


@pytest.mark.integration
def test_rejects_an_unknown_level():
    result = simulate_intervention(["ID3173040002"], [{"type": "cool_roof",
                                                       "level": "ekstrem"}])
    assert "error" in result


@pytest.mark.integration
def test_rejects_an_empty_intervention_list():
    result = simulate_intervention(["ID3173040002"], [])
    assert "error" in result


@pytest.mark.integration
def test_says_so_plainly_when_the_model_is_missing(monkeypatch):
    import teduh_agent.tools.scenario_tools as module

    class _NoBooster:
        booster = None

        def __getattr__(self, name):
            from teduh_agent.store import load

            return getattr(load(), name)

    monkeypatch.setattr(module, "get_store", lambda: _NoBooster())
    result = simulate_intervention(["ID3173040002"], [{"type": "cool_roof", "level": "low"}])
    assert "error" in result
    assert "model" in result["error"].lower()
```

- [ ] **Step 2: Jalankan tes untuk memastikan gagal**

Run: `uv run pytest tests/test_scenario_tools.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'teduh_agent.tools.scenario_tools'`

- [ ] **Step 3: Tulis `teduh_agent/tools/scenario_tools.py`**

```python
"""Agent-facing wrapper over model/scenario.py.

Two responsibilities the engine itself does not have. First, accepting the loose JSON shape
ADK hands over: an intervention may arrive as a named level or as explicit params, and
neither form may be trusted without validation. Second, attaching the literature comparison
CONCEPT §7.5 requires -- a model number presented with no published range beside it is
precisely the overclaiming this product exists to avoid.

The training frame and its quantiles are cached because every scenario call needs them and
re-reading 75_636 rows per request would blow the latency target.
"""

from functools import lru_cache

import pandas as pd
from google.adk.tools import ToolContext

from model.scenario import (
    INTERVENTION_TYPES,
    LEVELS,
    PARAM_NAME,
    Intervention,
    from_level,
    simulate,
    training_quantiles,
)
from model.train import prepare
from teduh_agent.facts import SOURCE_MODEL, fact, record, source_assumption
from teduh_agent.store import get_store
from teduh_agent.tools.evidence import evidence_for

INDICATIVE_NOTE = (
    "Angka ini perkiraan model untuk suhu PERMUKAAN (LST), bukan suhu udara, dan "
    "bersifat indikatif untuk penyaringan awal. Bandingkan dengan rentang literatur."
)


@lru_cache(maxsize=1)
def training_frame() -> pd.DataFrame:
    """Model-ready grid, cached for the process."""
    return prepare(get_store().grid.reset_index())


@lru_cache(maxsize=1)
def quantiles() -> pd.Series:
    """99th percentile of each training feature, for the extrapolation flag."""
    return training_quantiles(training_frame())


def _parse(raw: dict) -> Intervention:
    itype = raw.get("type")
    if itype not in INTERVENTION_TYPES:
        raise ValueError(
            f"jenis intervensi {itype!r} tidak dikenal; pilihan: {', '.join(INTERVENTION_TYPES)}"
        )
    if "level" in raw and raw["level"] is not None:
        level = raw["level"]
        if level not in LEVELS[itype]:
            raise ValueError(
                f"level {level!r} tidak dikenal untuk {itype}; pilihan: rendah/sedang/tinggi "
                f"({', '.join(LEVELS[itype])})"
            )
        return from_level(itype, level)

    params = raw.get("params") or {}
    key = PARAM_NAME[itype]
    if key not in params:
        raise ValueError(f"intervensi {itype} butuh level atau params[{key!r}]")
    return Intervention(itype, {key: float(params[key])})


def _facts_for(result, cost_sources: tuple[str, ...]) -> list:
    prefix = f"sim.{result.kel_id}"
    price_source = (
        cost_sources[0] if cost_sources else source_assumption("costs.unknown")
    )
    return [
        fact(f"{prefix}.delta_lst", "Perkiraan perubahan suhu permukaan",
             result.delta_lst_c, "degC", SOURCE_MODEL),
        fact(f"{prefix}.delta_lst_pop", "Perubahan suhu permukaan tertimbang penduduk",
             result.delta_lst_pop_weighted_c, "degC", SOURCE_MODEL),
        fact(f"{prefix}.vulnerable_benefiting", "Warga rentan yang merasakan pendinginan",
             result.vulnerable_benefiting, "jiwa", SOURCE_MODEL),
        fact(f"{prefix}.area", "Luas area intervensi", result.area_m2, "m2", SOURCE_MODEL),
        fact(f"{prefix}.cost", "Perkiraan biaya intervensi", result.cost_idr, "IDR",
             price_source),
    ]


def simulate_intervention(
    kel_ids: list[str],
    interventions: list[dict],
    tool_context: ToolContext | None = None,
) -> dict:
    """Simulasikan dampak intervensi pendinginan pada satu atau beberapa kelurahan.

    Menghitung perkiraan penurunan suhu permukaan, jumlah warga rentan yang merasakannya,
    luas area, dan biayanya. Selalu disertai rentang dari literatur sebagai pembanding.

    Args:
        kel_ids: daftar kode kelurahan, misalnya ["ID3173040002"].
        interventions: daftar intervensi. Setiap item berisi `type`
            ("tree_planting", "cool_roof", atau "green_roof") dan salah satu dari
            `level` ("low", "medium", "high") atau `params`
            ({"canopy_increase_pp": 7.5} untuk pohon, {"adoption_rate": 0.5} untuk atap).

    Returns:
        dict dengan `results` per kelurahan, `evidence` berisi pembanding literatur,
        `note` tentang keterbatasan, dan `facts`.
    """
    if not interventions:
        return {"error": "Belum ada intervensi yang dipilih untuk disimulasikan.", "facts": []}

    store = get_store()
    if store.booster is None:
        return {
            "error": (
                "Model panas belum tersedia, jadi simulasi tidak bisa dijalankan. "
                "Jalankan model.train lebih dulu."
            ),
            "facts": [],
        }

    try:
        parsed = [_parse(raw) for raw in interventions]
    except ValueError as error:
        return {"error": str(error), "facts": []}

    frame = training_frame()
    known = set(frame["kel_id"].unique())
    missing = [kel_id for kel_id in kel_ids if kel_id not in known]
    if missing:
        return {
            "error": f"Kelurahan tidak ada di data TEDUH: {', '.join(missing)}",
            "facts": [],
        }

    results: list[dict] = []
    facts: list = []
    for kel_id in kel_ids:
        cells = frame[frame["kel_id"] == kel_id]
        outcome = simulate(
            cells, parsed, store.booster, store.scenario_cfg, store.costs_cfg, quantiles()
        )
        results.append(
            {
                "kel_id": outcome.kel_id,
                "delta_lst_c": outcome.delta_lst_c,
                "delta_lst_pop_weighted_c": outcome.delta_lst_pop_weighted_c,
                "vulnerable_benefiting": outcome.vulnerable_benefiting,
                "area_m2": outcome.area_m2,
                "area_by_type": outcome.area_by_type,
                "cost_idr": outcome.cost_idr,
                "extrapolation": outcome.extrapolation,
                "extrapolated_features": list(outcome.extrapolated_features),
                "n_cells": outcome.n_cells,
            }
        )
        facts.extend(_facts_for(outcome, outcome.cost_sources))

    evidence: list[dict] = []
    for intervention in parsed:
        found = evidence_for(intervention.type)
        evidence.extend(found["evidence"])
        facts.extend(found["facts"])

    record(tool_context, facts)
    return {
        "results": results,
        "interventions": [
            {"type": item.type, "params": item.params} for item in parsed
        ],
        "evidence": evidence,
        "note": INDICATIVE_NOTE,
        "map_highlight": list(kel_ids),
        "facts": facts,
    }
```

- [ ] **Step 4: Jalankan tes untuk memastikan lulus**

Run: `uv run pytest tests/test_scenario_tools.py -v`
Expected: PASS. Butuh `teduh_agent/tools/evidence.py` dari Task M3-T6 — kerjakan T6 lebih dulu kalau mau urutan impor bersih.

- [ ] **Step 5: Commit**

```bash
git add teduh_agent/tools/scenario_tools.py tests/test_scenario_tools.py
git commit -m "feat: tambah tool simulate_intervention dengan pembanding literatur

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task M3-T5: Tool optimasi portofolio

**Files:**
- Create: `teduh_agent/tools/optimize.py`
- Test: `tests/test_optimize.py`

**Interfaces:**
- Consumes: `model.scenario.{INTERVENTION_TYPES, LEVELS, from_level, simulate}` (M3-T1); `teduh_agent.tools.scenario_tools.{training_frame, quantiles}` (M3-T4); `teduh_agent.tools.areas.directory` (M3-T3); `teduh_agent.store.{config_entry, get_store}`.
- Produces:
  - `LAMBDA_GENERAL_POP = 0.1`, `TOP_QUINTILE = 0.2`, `IDR_SCALE = 1_000_000`, `SOLVER_TIME_LIMIT_S = 20.0`, `MAX_CANDIDATE_AREAS = 40`
  - `Candidate` — frozen dataclass `(kel_id, intervention_type, level, value, cost_idr, delta_lst_c, vulnerable_benefiting, area_m2, in_top_quintile)`
  - `build_candidates(kel_ids: list[str]) -> list[Candidate]`
  - `solve(candidates, budget_idr: int, equity_share: float) -> tuple[list[Candidate], str]`
  - `optimize_portfolio(scope: str = "all", budget_idr: int = 0, equity_share: float | None = None, allowed: list[str] | None = None, tool_context: ToolContext | None = None) -> dict`

**Kenapa biaya diskalakan:** CP-SAT bekerja dengan integer. Anggaran Rp 2 miliar dalam rupiah penuh membuat koefisien raksasa dan solver lambat. Biaya dibulatkan ke **juta rupiah** (`IDR_SCALE`), yang membuat galat pembulatan maksimal Rp 1 juta per paket — tidak berarti pada skala anggaran dinas, dan kendala anggaran tetap dijamin karena pembulatan dilakukan **ke atas**.

- [ ] **Step 1: Tulis tes yang gagal**

Buat `tests/test_optimize.py`:

```python
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
def test_candidates_cover_every_intervention_and_level(candidates):
    from model.scenario import INTERVENTION_TYPES, LEVELS

    expected = len({"ID3173040002", "ID3172030001", "ID3172070002"}) * sum(
        len(LEVELS[itype]) for itype in INTERVENTION_TYPES
    )
    assert len(candidates) == expected


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
    chosen, status = solve(candidates, BUDGET_2B, equity_share=0.6)
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
def test_tool_emits_facts_for_the_budget_and_the_totals():
    result = optimize_portfolio("ID3173", BUDGET_2B)
    if "error" in result:
        pytest.skip(result["error"])
    ids = {f["id"] for f in result["facts"]}
    assert {"opt.budget", "opt.total_cost", "opt.equity_share", "opt.n_packages"} <= ids


@pytest.mark.integration
def test_tool_can_restrict_the_allowed_interventions():
    result = optimize_portfolio("ID3173", BUDGET_2B, allowed=["cool_roof"])
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


@pytest.mark.unit
def test_general_population_is_weighted_below_vulnerable_residents():
    # Equity is the point of the product: a general resident must not count as much as a
    # toddler or an elderly resident.
    assert 0 < LAMBDA_GENERAL_POP < 1


@pytest.mark.unit
def test_top_quintile_is_one_fifth():
    assert TOP_QUINTILE == pytest.approx(0.2)
```

- [ ] **Step 2: Jalankan tes untuk memastikan gagal**

Run: `uv run pytest tests/test_optimize.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'teduh_agent.tools.optimize'`

- [ ] **Step 3: Tulis `teduh_agent/tools/optimize.py`**

```python
"""Budget portfolio selection with OR-Tools CP-SAT (CONCEPT §7.6).

This is the tool that puts a spending plan in front of a city, so two constraints are
hard rather than advisory: total cost must not exceed the budget, and at least
`equity_share` of the spend must land in the top HVI quintile. Without the second one the
optimiser does exactly what a cost-per-degree objective asks and spends the money where
land is cheap and empty, which is the opposite of the product's purpose.

Costs are scaled to millions of rupiah because CP-SAT is integer-only and a Rp 2 billion
budget in whole rupiah produces coefficients large enough to slow the solver badly. Each
package's cost is rounded UP, so the budget constraint stays conservative: the plan can come
in under budget by up to Rp 1 million per package, never over.

Candidate generation runs the scenario engine once per (kelurahan x intervention x level),
which is why MAX_CANDIDATE_AREAS exists -- all 264 kelurahan would be 2_376 simulations and
would blow the latency target.
"""

import math
from dataclasses import dataclass

from google.adk.tools import ToolContext
from ortools.sat.python import cp_model

from model.scenario import INTERVENTION_TYPES, LEVELS, from_level, simulate
from teduh_agent.facts import SOURCE_MODEL, fact, record
from teduh_agent.store import config_entry, get_store
from teduh_agent.tools.areas import directory
from teduh_agent.tools.scenario_tools import quantiles, training_frame

# Weight on general population relative to a vulnerable resident. Deliberately well below 1:
# equity is the product's purpose, so a toddler or an elderly resident must count for more.
LAMBDA_GENERAL_POP = 0.1

# "Top HVI quintile" (CONCEPT §7.6).
TOP_QUINTILE = 0.2

# CP-SAT is integer-only; work in millions of rupiah.
IDR_SCALE = 1_000_000

SOLVER_TIME_LIMIT_S = 20.0

# Each area costs 9 scenario simulations, so the candidate set is capped by HVI rank.
MAX_CANDIDATE_AREAS = 40

# Objective is scaled to an integer too; value is in person-degrees.
VALUE_SCALE = 100


@dataclass(frozen=True)
class Candidate:
    """One (kelurahan, intervention, level) package the solver may buy."""

    kel_id: str
    intervention_type: str
    level: str
    value: float
    cost_idr: float
    delta_lst_c: float
    vulnerable_benefiting: float
    area_m2: float
    in_top_quintile: bool


def _top_quintile_ids() -> set[str]:
    kelurahan = get_store().kelurahan
    cutoff = max(1, int(round(len(kelurahan) * TOP_QUINTILE)))
    return set(kelurahan.nsmallest(cutoff, "hvi_rank").index)


def build_candidates(kel_ids: list[str], allowed: list[str] | None = None) -> list[Candidate]:
    """Simulate every intervention and level for each area, as solver input."""
    store = get_store()
    frame = training_frame()
    q99 = quantiles()
    equitable = _top_quintile_ids()
    types = [t for t in INTERVENTION_TYPES if allowed is None or t in allowed]

    candidates: list[Candidate] = []
    for kel_id in kel_ids:
        cells = frame[frame["kel_id"] == kel_id]
        if cells.empty:
            continue
        vulnerable = float((cells["pop_u5"].fillna(0) + cells["pop_65p"].fillna(0)).sum())
        general = float(cells["pop"].fillna(0).sum())
        people = vulnerable + LAMBDA_GENERAL_POP * general

        for itype in types:
            for level in LEVELS[itype]:
                outcome = simulate(
                    cells,
                    [from_level(itype, level)],
                    store.booster,
                    store.scenario_cfg,
                    store.costs_cfg,
                    q99,
                )
                candidates.append(
                    Candidate(
                        kel_id=kel_id,
                        intervention_type=itype,
                        level=level,
                        value=people * max(0.0, -outcome.delta_lst_c),
                        cost_idr=outcome.cost_idr,
                        delta_lst_c=outcome.delta_lst_c,
                        vulnerable_benefiting=outcome.vulnerable_benefiting,
                        area_m2=outcome.area_m2,
                        in_top_quintile=kel_id in equitable,
                    )
                )
    return candidates


def solve(
    candidates: list[Candidate], budget_idr: int, equity_share: float
) -> tuple[list[Candidate], str]:
    """Multiple-choice knapsack: maximise value within budget and equity constraints."""
    affordable = [c for c in candidates if c.cost_idr > 0 and c.cost_idr <= budget_idr]
    if not affordable or budget_idr <= 0:
        return [], "NO_AFFORDABLE_CANDIDATE"

    model = cp_model.CpModel()
    picked = [model.NewBoolVar(f"pick_{i}") for i in range(len(affordable))]

    # Round each cost UP so the plan can only come in under budget, never over.
    costs = [math.ceil(c.cost_idr / IDR_SCALE) for c in affordable]
    budget_scaled = budget_idr // IDR_SCALE

    model.Add(sum(cost * var for cost, var in zip(costs, picked, strict=True)) <= budget_scaled)

    # At most one level per (kelurahan, intervention).
    groups: dict[tuple[str, str], list] = {}
    for index, candidate in enumerate(affordable):
        groups.setdefault((candidate.kel_id, candidate.intervention_type), []).append(
            picked[index]
        )
    for members in groups.values():
        model.AddAtMostOne(members)

    # Equity: spend in the top HVI quintile must be at least equity_share of total spend.
    # Written as a linear inequality so CP-SAT can handle it directly.
    if equity_share > 0:
        weighted = []
        for index, candidate in enumerate(affordable):
            coefficient = costs[index] * (
                (1.0 - equity_share) if candidate.in_top_quintile else -equity_share
            )
            weighted.append((round(coefficient * 1000), picked[index]))
        model.Add(sum(scaled * var for scaled, var in weighted) >= 0)

    model.Maximize(
        sum(
            round(candidate.value * VALUE_SCALE) * picked[index]
            for index, candidate in enumerate(affordable)
        )
    )

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = SOLVER_TIME_LIMIT_S
    solver.parameters.num_search_workers = 4
    status = solver.Solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return [], solver.StatusName(status)

    chosen = [
        candidate
        for index, candidate in enumerate(affordable)
        if solver.Value(picked[index]) == 1
    ]
    return chosen, solver.StatusName(status)


def _candidate_areas(scope: str) -> list[str]:
    """The highest-HVI areas in scope, capped so candidate generation stays fast."""
    frame = directory()
    if scope and scope.lower() != "all":
        if scope in frame["kota_id"].values:
            frame = frame[frame["kota_id"] == scope]
        elif scope in frame["kec_id"].values:
            frame = frame[frame["kec_id"] == scope]
        elif scope in frame.index:
            frame = frame.loc[[scope]]
        else:
            from teduh_agent.tools.areas import find_area

            located = find_area(scope)
            if not located["matches"]:
                return []
            frame = frame.loc[[m["kel_id"] for m in located["matches"]]]
    return list(frame.nsmallest(min(MAX_CANDIDATE_AREAS, len(frame)), "hvi_rank").index)


def optimize_portfolio(
    scope: str = "all",
    budget_idr: int = 0,
    equity_share: float | None = None,
    allowed: list[str] | None = None,
    tool_context: ToolContext | None = None,
) -> dict:
    """Susun paket intervensi terbaik dalam batas anggaran, dengan kendala keadilan.

    Memilih kombinasi kelurahan dan intervensi yang memaksimalkan pendinginan tertimbang
    jumlah warga rentan per rupiah, dengan jaminan total biaya tidak melewati anggaran dan
    minimal sebagian anggaran masuk ke kelurahan paling rentan.

    Args:
        scope: "all" untuk seluruh DKI, atau nama/kode kota atau kecamatan.
        budget_idr: anggaran total dalam rupiah, misalnya 2000000000 untuk Rp 2 miliar.
        equity_share: porsi minimum anggaran untuk kuintil HVI teratas, 0 sampai 1.
            Kalau kosong, memakai 0,6 dari config.
        allowed: opsional, batasi jenis intervensi, misalnya ["cool_roof"].

    Returns:
        dict dengan `packages`, `total_cost_idr`, `equity_share_achieved`,
        `map_highlight`, dan `facts`.
    """
    if budget_idr <= 0:
        return {"error": "Anggaran harus lebih besar dari nol.", "facts": []}

    store = get_store()
    if store.booster is None:
        return {
            "error": "Model panas belum tersedia. Jalankan model.train lebih dulu.",
            "facts": [],
        }

    configured, _ = config_entry(store.costs_cfg, "optimizer", "equity_share_min")
    requested = float(configured) if equity_share is None else float(equity_share)
    if not 0.0 <= requested <= 1.0:
        return {"error": "Porsi keadilan harus antara 0 dan 1.", "facts": []}

    if allowed is not None:
        unknown = [t for t in allowed if t not in INTERVENTION_TYPES]
        if unknown:
            return {"error": f"Jenis intervensi tidak dikenal: {', '.join(unknown)}", "facts": []}

    areas = _candidate_areas(scope)
    if not areas:
        return {"error": f"Wilayah {scope!r} tidak ada di data TEDUH.", "facts": []}

    candidates = build_candidates(areas, allowed)
    chosen, status = solve(candidates, int(budget_idr), requested)

    if not chosen:
        return {
            "error": (
                f"Tidak ada paket yang bisa dipilih dengan anggaran Rp {budget_idr:,} dan "
                f"porsi keadilan {requested:.0%} (status solver: {status}). "
                "Coba naikkan anggaran atau turunkan porsi keadilan."
            ),
            "packages": [],
            "facts": [],
        }

    total_cost = sum(c.cost_idr for c in chosen)
    equitable_cost = sum(c.cost_idr for c in chosen if c.in_top_quintile)
    achieved = equitable_cost / total_cost if total_cost else 0.0
    names = directory()["kel_name"]

    packages = [
        {
            "kel_id": c.kel_id,
            "kel_name": names.get(c.kel_id, c.kel_id),
            "intervention_type": c.intervention_type,
            "level": c.level,
            "cost_idr": c.cost_idr,
            "delta_lst_c": c.delta_lst_c,
            "vulnerable_benefiting": c.vulnerable_benefiting,
            "area_m2": c.area_m2,
            "in_top_hvi_quintile": c.in_top_quintile,
        }
        for c in sorted(chosen, key=lambda c: -c.value)
    ]

    facts = [
        fact("opt.budget", "Anggaran yang tersedia", float(budget_idr), "IDR", SOURCE_MODEL),
        fact("opt.total_cost", "Total biaya portofolio", total_cost, "IDR", SOURCE_MODEL),
        fact("opt.n_packages", "Jumlah paket terpilih", len(chosen), "paket", SOURCE_MODEL),
        fact("opt.equity_share", "Porsi anggaran untuk kuintil HVI teratas", achieved, "fraksi",
             SOURCE_MODEL),
        fact("opt.total_cooling", "Total pendinginan tertimbang penduduk",
             sum(c.value for c in chosen), "jiwa-derajat", SOURCE_MODEL),
        fact("opt.vulnerable_reached", "Warga rentan yang merasakan pendinginan",
             sum(c.vulnerable_benefiting for c in chosen), "jiwa", SOURCE_MODEL),
    ]
    record(tool_context, facts)

    return {
        "packages": packages,
        "total_cost_idr": total_cost,
        "budget_idr": float(budget_idr),
        "equity_share_requested": requested,
        "equity_share_achieved": achieved,
        "solver_status": status,
        "n_candidates": len(candidates),
        "note": (
            "Perkiraan biaya memakai harga satuan dari config/costs.yaml. "
            "Pendinginan adalah suhu permukaan dan bersifat indikatif."
        ),
        "map_highlight": [p["kel_id"] for p in packages],
        "facts": facts,
    }
```

- [ ] **Step 4: Jalankan tes untuk memastikan lulus**

Run: `uv run pytest tests/test_optimize.py -v`
Expected: PASS, 18 tes. Butuh waktu beberapa puluh detik karena setiap kandidat menjalankan simulasi.

- [ ] **Step 5: Verifikasi kendala pada anggaran nyata Rp 2 miliar**

```bash
uv run python -c "
from teduh_agent.tools.optimize import optimize_portfolio
r = optimize_portfolio('all', 2_000_000_000)
if 'error' in r:
    print('GAGAL:', r['error']); raise SystemExit(1)
print(f\"paket           : {len(r['packages'])}\")
print(f\"total biaya     : Rp {r['total_cost_idr']:,.0f} dari Rp {r['budget_idr']:,.0f}\")
print(f\"porsi keadilan  : diminta {r['equity_share_requested']:.0%}, tercapai {r['equity_share_achieved']:.0%}\")
assert r['total_cost_idr'] <= r['budget_idr'], 'anggaran terlampaui'
assert r['equity_share_achieved'] >= r['equity_share_requested'] - 1e-6, 'kendala keadilan gagal'
for p in r['packages'][:8]:
    print(f\"  {p['kel_name'][:20]:20s} {p['intervention_type']:14s} {p['level']:7s} \"
          f\"Rp {p['cost_idr']:14,.0f}  dLST {p['delta_lst_c']:+6.3f}  \"
          f\"kuintil-atas {p['in_top_hvi_quintile']}\")
print('kendala terpenuhi')
"
```
Expected: `kendala terpenuhi`, dan sebagian besar paket berada di kuintil HVI teratas.

- [ ] **Step 6: Commit**

```bash
git add teduh_agent/tools/optimize.py tests/test_optimize.py
git commit -m "feat: tambah optimize_portfolio dengan CP-SAT, anggaran dan kendala keadilan

Biaya dibulatkan ke atas ke juta rupiah, jadi kendala anggaran selalu konservatif.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task M3-T6: Tool basis bukti

**Files:**
- Create: `teduh_agent/tools/evidence.py`
- Test: `tests/test_evidence.py`

**Interfaces:**
- Consumes: `teduh_agent.store.get_store`; `teduh_agent.facts.{fact, record, source_evidence}`.
- Produces:
  - `COMPARABLE_METRIC = "lst_change_c"`
  - `evidence_for(intervention: str) -> dict` — fungsi murni tanpa `tool_context`, dipakai juga oleh `scenario_tools.py`
  - `get_evidence(intervention: str, tool_context: ToolContext | None = None) -> dict`

**Kenapa dua fungsi:** `scenario_tools.simulate_intervention` perlu bukti tanpa mencatat ulang fakta ke ledger dua kali. `evidence_for` adalah bagian murninya; `get_evidence` adalah pembungkus ADK yang mencatat.

- [ ] **Step 1: Tulis tes yang gagal**

Buat `tests/test_evidence.py`:

```python
"""The evidence base is what keeps a model number honest. The metric-comparability test is
the important one: interventions.json records roof SURFACE temperature drops of up to 13 C,
and presenting that next to an area-average LST change of -0.8 C would be badly misleading
even though both are real published figures."""

import pytest

from teduh_agent.tools.evidence import COMPARABLE_METRIC, evidence_for, get_evidence


class FakeToolContext:
    def __init__(self) -> None:
        self.state: dict = {}


@pytest.mark.integration
def test_returns_evidence_for_each_simulated_intervention():
    for intervention in ("tree_planting", "cool_roof", "green_roof"):
        result = evidence_for(intervention)
        assert result["evidence"], f"tidak ada bukti untuk {intervention}"


@pytest.mark.integration
def test_every_entry_is_citable():
    for entry in evidence_for("tree_planting")["evidence"]:
        assert entry["source_title"]
        assert entry["url_or_doi"]
        assert entry["year"]


@pytest.mark.integration
def test_entries_declare_whether_their_metric_is_comparable_to_model_output():
    # A roof-surface temperature drop is not an area cooling. The flag makes the agent
    # able to say so instead of putting the two side by side as equals.
    for entry in evidence_for("cool_roof")["evidence"]:
        assert "comparable_to_model" in entry
        assert entry["comparable_to_model"] == (entry["metric"] == COMPARABLE_METRIC)


@pytest.mark.integration
def test_comparable_entries_are_listed_first():
    entries = evidence_for("cool_roof")["evidence"]
    flags = [entry["comparable_to_model"] for entry in entries]
    assert flags == sorted(flags, reverse=True)


@pytest.mark.integration
def test_tree_planting_surfaces_the_kuala_lumpur_ndvi_range():
    # CONCEPT §7.5 names this as the comparison to show: -1.4 to 0.1 degC for +25% NDVI.
    entries = evidence_for("tree_planting")["evidence"]
    kl = next(e for e in entries if e["id"] == "ev_ndvi_kl_2025")
    assert kl["value_min"] == pytest.approx(-1.4)
    assert kl["value_max"] == pytest.approx(0.1)
    assert kl["comparable_to_model"] is True


@pytest.mark.integration
def test_facts_cite_the_evidence_id_as_their_source():
    for entry in evidence_for("tree_planting")["facts"]:
        assert entry["source"].startswith("evidence:")


@pytest.mark.integration
def test_facts_record_both_bounds_of_a_range():
    ids = {f["id"] for f in evidence_for("tree_planting")["facts"]}
    assert "evidence.ev_ndvi_kl_2025.min" in ids
    assert "evidence.ev_ndvi_kl_2025.max" in ids


@pytest.mark.integration
def test_unknown_intervention_says_so_without_inventing_evidence():
    result = evidence_for("teleportasi")
    assert result["evidence"] == []
    assert "error" in result
    assert result["facts"] == []


@pytest.mark.integration
def test_get_evidence_records_into_the_session_ledger():
    ctx = FakeToolContext()
    get_evidence("cool_roof", ctx)
    assert ctx.state["facts"]


@pytest.mark.integration
def test_get_evidence_does_not_record_for_an_unknown_intervention():
    ctx = FakeToolContext()
    get_evidence("teleportasi", ctx)
    assert ctx.state.get("facts", []) == []
```

- [ ] **Step 2: Jalankan tes untuk memastikan gagal**

Run: `uv run pytest tests/test_evidence.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'teduh_agent.tools.evidence'`

- [ ] **Step 3: Tulis `teduh_agent/tools/evidence.py`**

```python
"""Published findings that put a model number in context (CONCEPT §7.7).

The comparable_to_model flag is the part that matters. interventions.json deliberately
records several metrics, and only lst_change_c is the same quantity the model predicts. A
cool roof study reporting an 11.58 C drop is measuring the ROOF SKIN; putting that beside an
area-average LST change of -0.8 C would be misleading even though both figures are real and
published. Flagging it lets the agent cite the study while saying plainly what it measured.

evidence_for() is the pure half, used by scenario_tools so a single scenario answer does not
record the same facts into the ledger twice. get_evidence() is the ADK wrapper that records.
"""

from google.adk.tools import ToolContext

from teduh_agent.facts import fact, record, source_evidence
from teduh_agent.store import get_store

# The only metric directly comparable to the model's output.
COMPARABLE_METRIC = "lst_change_c"


def evidence_for(intervention: str) -> dict:
    """Evidence entries for one intervention, comparable metrics first."""
    store = get_store()
    matching = [
        entry for entry in store.evidence if entry["intervention"] == intervention
    ]
    if not matching:
        known = sorted({entry["intervention"] for entry in store.evidence})
        return {
            "error": (
                f"Tidak ada entri bukti untuk {intervention!r}. "
                f"Yang tersedia: {', '.join(known)}."
            ),
            "evidence": [],
            "facts": [],
        }

    entries = [
        {**entry, "comparable_to_model": entry["metric"] == COMPARABLE_METRIC}
        for entry in matching
    ]
    entries.sort(key=lambda entry: not entry["comparable_to_model"])

    facts = []
    for entry in entries:
        for bound in ("min", "max"):
            facts.append(
                fact(
                    f"evidence.{entry['id']}.{bound}",
                    f"{entry['source_title']} ({entry['year']}), batas {bound}",
                    entry[f"value_{bound}"],
                    entry["unit"],
                    source_evidence(entry["id"]),
                )
            )

    return {
        "evidence": entries,
        "note": (
            "Hanya entri dengan comparable_to_model=true yang mengukur besaran yang sama "
            "dengan keluaran model (perubahan suhu permukaan per wilayah)."
        ),
        "facts": facts,
    }


def get_evidence(intervention: str, tool_context: ToolContext | None = None) -> dict:
    """Ambil temuan literatur untuk satu jenis intervensi pendinginan.

    Pakai tool ini setiap kali merekomendasikan intervensi, supaya angka model selalu
    disertai rentang dari studi yang sudah diterbitkan beserta sitasinya.

    Args:
        intervention: "tree_planting", "cool_roof", "green_roof", "cool_pavement",
            "green_curtain", atau "combined_package".

    Returns:
        dict dengan `evidence` (entri bersitasi, yang sebanding lebih dulu), `note`,
        dan `facts`.
    """
    result = evidence_for(intervention)
    record(tool_context, result["facts"])
    return result
```

- [ ] **Step 4: Jalankan tes untuk memastikan lulus**

Run: `uv run pytest tests/test_evidence.py -v`
Expected: PASS, 10 tes.

- [ ] **Step 5: Jalankan seluruh suite tool**

Run: `uv run pytest tests/test_areas.py tests/test_scenario_tools.py tests/test_optimize.py tests/test_evidence.py -q`
Expected: hijau semua.

- [ ] **Step 6: Commit**

```bash
git add teduh_agent/tools/evidence.py tests/test_evidence.py
git commit -m "feat: tambah get_evidence dengan penanda metrik yang sebanding

Temuan suhu permukaan atap tidak lagi bisa disajikan sebagai pendinginan kawasan.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Definisi M3b selesai

- [ ] Tujuh tool ada dengan nama persis seperti di `tests/eval/golden_questions.yaml`.
- [ ] Setiap tool mengembalikan `facts`, dan setiap angka di payload punya `Fact` yang bersumber.
- [ ] `find_area("Jakarta Timur")` mengembalikan lebih dari 50 kelurahan — artinya join GeoJSON berhasil.
- [ ] `rank_priority_areas` dengan bobot kustom mengubah urutan dan melaporkan bobot yang dipakai.
- [ ] `optimize_portfolio` dengan Rp 2 miliar: total biaya ≤ anggaran dan porsi keadilan ≥ 60%.
- [ ] Kondisi infeasible dijawab dengan penjelasan, bukan exception.
- [ ] `uv run pytest -q` hijau.

**Selanjutnya:** [`m3-api.md`](m3-api.md) — REST API di atas tool yang sama.
