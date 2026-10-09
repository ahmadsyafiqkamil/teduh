# M0 — Kerangka Repo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> Baca `docs/superpowers/plans/README.md` bagian **Global Constraints** dan **Interface Registry** sebelum mulai. Semua nama tipe dan fungsi di sini terdaftar di sana.

**Goal:** Membuat kerangka paket Python yang bisa di-install, memuat artefak data M1 ke memori, dan menjalankan satu agen ADK dengan satu tool nyata — lokal lewat `adk web` dan di Cloud Run.

**Architecture:** Dua modul fondasi yang dipakai semua milestone berikutnya: `teduh_agent/store.py` memuat seluruh artefak sekali (lru_cache singleton) karena Earth Engine tidak boleh dipanggil saat runtime, dan `teduh_agent/facts.py` menyediakan tipe `Fact` yang menjadi satu-satunya jalan angka boleh sampai ke LLM. Agen M0 sengaja hanya punya satu tool supaya jalur deploy terbukti sebelum logika domain masuk.

**Tech Stack:** Python 3.12, uv, google-adk, pandas, pyarrow, pyyaml, lightgbm (untuk memuat booster nanti), FastAPI, pytest, Docker, Cloud Run.

## Global Constraints

- Python **3.12**, manajer paket **`uv`**. `earthengine-api` hanya di dependency group `pipeline`, tidak pernah di runtime.
- Model Gemini dari env **`TEDUH_MODEL`**, default `gemini-3.8-flash`. **Jangan hard-code model ID.**
- Paket ADK di `teduh_agent/` dengan `root_agent` di `agent.py` dan `from . import agent` di `__init__.py`.
- Setiap tool mengembalikan `dict` dengan kunci `facts: list[Fact]`. Tidak ada angka tanpa `facts` (CLAUDE.md aturan 2).
- Setiap entri `config/*.yaml` wajib punya `value` dan `source`. Pembaca config harus menolak entri tanpa `source` (CLAUDE.md aturan 4).
- Identifier dan komentar kode: **Inggris**. `print()` dan teks pengguna: **Bahasa Indonesia** (CLAUDE.md aturan 7).
- Jangan commit kredensial atau data mentah besar (CLAUDE.md aturan 8).
- Ikuti pola `pipeline/*.py`: docstring modul menjelaskan *kenapa*, konstanta `UPPER_SNAKE` di atas, `main()` lalu `check()` yang meng-assert invarian.
- Angka acuan nyata: 264 kelurahan, 75.636 sel, 75.608 `good` + 28 `low`, rata-rata LST kota 41,8376 °C.
- Commit: conventional commits, diakhiri `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`.

---

## File Structure

| File | Tanggung jawab |
|---|---|
| `pyproject.toml` | Satu sumber kebenaran dependensi, paket yang di-build, konfigurasi pytest dan ruff. |
| `.env.example` | Daftar env var yang dibaca kode, tanpa nilai rahasia. |
| `.gitignore` | Ditambah `data/model/`, `web/node_modules/`, `web/.next/`, `.env`. |
| `teduh_agent/facts.py` | Tipe `Fact` + ledger fakta per sesi. Tanpa logika domain, tanpa format angka. |
| `teduh_agent/store.py` | Memuat seluruh artefak sekali. Pembaca config yang menolak entri tanpa `source`. |
| `teduh_agent/agent.py` | `root_agent` ADK. M0: satu tool. M4 menggantinya dengan koordinator + sub-agen. |
| `teduh_agent/__init__.py` | `from . import agent` — wajib agar ADK menemukan agen. |
| `model/__init__.py` | Menandai `model/` sebagai paket agar `model.hvi` dkk bisa diimpor di M2. |
| `tests/conftest.py` | Fixture `fixture_store` (data kecil) dan `real_store` (dilewati kalau artefak tidak ada). |
| `infra/Dockerfile` | Image Cloud Run: Python 3.12 + dependensi sistem WeasyPrint + artefak data dibakar ke image. |
| `infra/cloudbuild.yaml` | Build dengan `-f infra/Dockerfile` karena Dockerfile tidak di root. |
| `infra/deploy_api.sh` | Build + deploy, menolak jalan kalau artefak data belum ada. |

**Keputusan yang dikunci di sini:** artefak data **dibakar ke dalam image Docker** (total ~9,3 MB), bukan diunduh dari GCS saat startup. Ini menyimpang dari CONCEPT §11.1 yang memakai `TEDUH_DATA_URI=gs://...`. Alasannya: 9 MB terlalu kecil untuk membenarkan jalur GCS + kredensial + penanganan gagal-unduh, dan membakarnya menghilangkan satu titik gagal saat penilaian. `TEDUH_DATA_DIR` disediakan untuk menunjuk direktori lain (dipakai tes). **Catat penyimpangan ini di `docs/DECISIONS.md` pada Task M0-T5.**

---

## Task M0-T1: Manifest paket dan dependensi

**Files:**
- Create: `pyproject.toml`
- Create: `.env.example`
- Create: `model/__init__.py`
- Create: `data/model/.gitkeep`
- Modify: `.gitignore` (tambah blok di akhir)

**Interfaces:**
- Consumes: tidak ada (task pertama).
- Produces: `uv sync` menghasilkan `.venv` dan `uv.lock`; `uv run pytest` bisa dijalankan; paket `teduh_agent`, `model`, `api` bisa diimpor.

- [ ] **Step 1: Inisialisasi git (repo belum di-init)**

```bash
cd /Users/ahmadsyafiqkamil/Documents/Project/Teduh
git init
git add -A
git commit -m "chore: snapshot pekerjaan M1 (data pipeline) sebelum M0"
```

- [ ] **Step 2: Tulis `pyproject.toml`**

```toml
[project]
name = "teduh"
version = "0.1.0"
description = "AI agent untuk perencanaan mitigasi Urban Heat Island tingkat kelurahan"
requires-python = ">=3.12,<3.13"
dependencies = [
    "google-adk>=1.0",
    "google-genai>=1.0",
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "pydantic>=2.7",
    "pandas>=2.2",
    "pyarrow>=16",
    "numpy>=1.26",
    "pyyaml>=6.0",
    "lightgbm>=4.3",
    "shap>=0.45",
    "scikit-learn>=1.5",
    "ortools>=9.10",
    "markdown-it-py>=3.0",
    "weasyprint>=62",
]

[dependency-groups]
dev = [
    "pytest>=8.2",
    "pytest-cov>=5.0",
    "httpx>=0.27",
    "ruff>=0.5",
]
# Offline only. Never imported by teduh_agent/, model/, or api/ (CLAUDE.md rule 6).
pipeline = [
    "earthengine-api>=1.0",
    "google-api-python-client>=2.130",
    "geopandas>=1.0",
    "rasterio>=1.3",
    "scipy>=1.13",
    "openpyxl>=3.1",
    "pypdf>=4.2",
    "pillow>=10.3",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["teduh_agent", "model", "api"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-q --strict-markers"
markers = [
    "unit: fungsi murni, tanpa I/O",
    "integration: menyentuh artefak data atau HTTP",
    "slow: latih model atau panggil Gemini",
]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM"]

[tool.coverage.run]
source = ["teduh_agent", "model", "api"]
```

- [ ] **Step 3: Tulis `.env.example`**

```bash
# Salin ke .env dan isi. .env tidak pernah di-commit (CLAUDE.md aturan 8).

# Google Cloud / Gemini
GOOGLE_CLOUD_PROJECT=
GOOGLE_CLOUD_LOCATION=asia-southeast2
GOOGLE_GENAI_USE_ENTERPRISE=True

# Model ID dibaca dari env supaya tidak pernah hard-coded. Cek ulang di AI Studio
# sebelum deploy.
TEDUH_MODEL=gemini-3.8-flash

# Kosongkan untuk membaca artefak dari root repo. Diisi hanya kalau artefak ditaruh di
# direktori lain (dipakai tes dan container).
TEDUH_DATA_DIR=

# 1 = satu LlmAgent dengan semua tool, fallback kalau routing sub-agen tidak stabil
# (CONCEPT §8.1).
TEDUH_SINGLE_AGENT=0

# Dipakai saat deploy Cloud Run: 1 selama periode penilaian 19 Okt - 6 Nov (CONCEPT §14).
TEDUH_MIN_INSTANCES=0

# Frontend
NEXT_PUBLIC_TEDUH_API=http://localhost:8080
```

- [ ] **Step 4: Tulis `model/__init__.py`**

```python
"""Deterministic computation layer: HVI, heat model, scenario engine, costs.

Nothing here knows about ADK or HTTP. The tools in teduh_agent/tools/ wrap these functions
and attach provenance; the REST API in api/ calls the same functions directly. That split is
what keeps CLAUDE.md rule 1 enforceable -- the LLM can only reach numbers through code that
lives in this package.
"""
```

- [ ] **Step 5: Buat direktori artefak model dan perbarui `.gitignore`**

`data/model/` harus ada sebagai direktori sejak M0 karena `infra/Dockerfile` mem-`COPY` direktori itu, dan `COPY` atas direktori yang tidak ada akan menggagalkan build.

```bash
mkdir -p data/model
touch data/model/.gitkeep
```

Tambahkan di akhir `.gitignore`:

```gitignore
# Artefak model, dihasilkan ulang oleh model/train.py dan model/explain.py.
# .gitkeep tetap di-commit supaya direktorinya ada untuk COPY di infra/Dockerfile.
data/model/*
!data/model/.gitkeep

# Rahasia dan dependensi frontend.
.env
web/node_modules/
web/.next/
```

- [ ] **Step 6: Install dan verifikasi**

Run: `uv sync`
Expected: `.venv` dan `uv.lock` terbentuk, tanpa error resolusi.

Run: `uv run python -c "import model; print('model ok')"`
Expected: `model ok`

Run: `uv run pytest`
Expected: `no tests ran` dan **exit code 5**, bukan error konfigurasi.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml uv.lock .env.example .gitignore model/__init__.py data/model/.gitkeep
git commit -m "chore: tambah manifest paket uv dan kerangka paket model

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task M0-T2: Tipe Fact dan ledger fakta sesi

**Files:**
- Create: `teduh_agent/facts.py`
- Create: `teduh_agent/__init__.py` (sementara kosong; M0-T4 mengisinya)
- Test: `tests/test_facts.py`

**Interfaces:**
- Consumes: tidak ada.
- Produces:
  - `Fact = TypedDict("Fact", {"id": str, "label": str, "value": float | int | str, "unit": str, "source": str})`
  - `SOURCE_DATA = "data:grid_features@v1"`, `SOURCE_MODEL = "model:lgbm@v1"`, `STATE_KEY = "facts"`
  - `fact(id: str, label: str, value: float | int | str, unit: str, source: str) -> Fact`
  - `source_evidence(evidence_id: str) -> str`
  - `source_assumption(key: str) -> str`
  - `record(tool_context, facts: list[Fact]) -> None`
  - `session_facts(tool_context) -> list[Fact]`

- [ ] **Step 1: Tulis tes yang gagal**

Buat `tests/test_facts.py`:

```python
"""Facts are the provenance contract: if this file's rules bend, the brief validator in M5
has nothing solid to check against."""

import pytest

from teduh_agent.facts import (
    SOURCE_DATA,
    fact,
    record,
    session_facts,
    source_assumption,
    source_evidence,
)


class FakeToolContext:
    """Stands in for google.adk.tools.ToolContext, which only needs a mutable .state here."""

    def __init__(self) -> None:
        self.state: dict = {}


@pytest.mark.unit
def test_fact_carries_id_label_value_unit_and_source():
    # Arrange / Act
    result = fact("kel_ID3173040002.lst", "LST rata-rata", 44.61, "degC", SOURCE_DATA)

    # Assert
    assert result == {
        "id": "kel_ID3173040002.lst",
        "label": "LST rata-rata",
        "value": 44.61,
        "unit": "degC",
        "source": "data:grid_features@v1",
    }


@pytest.mark.unit
def test_fact_without_source_is_rejected():
    with pytest.raises(ValueError, match="source"):
        fact("kel_x.lst", "LST", 40.0, "degC", "")


@pytest.mark.unit
def test_fact_without_id_is_rejected():
    with pytest.raises(ValueError, match="id"):
        fact("", "LST", 40.0, "degC", SOURCE_DATA)


@pytest.mark.unit
def test_record_accumulates_facts_across_calls():
    # Arrange
    ctx = FakeToolContext()

    # Act
    record(ctx, [fact("a", "A", 1, "unit", SOURCE_DATA)])
    record(ctx, [fact("b", "B", 2, "unit", SOURCE_DATA)])

    # Assert
    assert {f["id"] for f in session_facts(ctx)} == {"a", "b"}


@pytest.mark.unit
def test_record_dedupes_by_id_keeping_the_newest_value():
    # Arrange
    ctx = FakeToolContext()

    # Act
    record(ctx, [fact("a", "A", 1, "unit", SOURCE_DATA)])
    record(ctx, [fact("a", "A", 99, "unit", SOURCE_DATA)])

    # Assert
    ledger = session_facts(ctx)
    assert len(ledger) == 1
    assert ledger[0]["value"] == 99


@pytest.mark.unit
def test_record_without_a_tool_context_is_a_supported_noop():
    # The REST API calls the same tool functions without an ADK session, so a missing
    # context must not raise -- there is simply no ledger to append to.
    record(None, [fact("a", "A", 1, "unit", SOURCE_DATA)])
    assert session_facts(None) == []


@pytest.mark.unit
def test_session_facts_returns_a_copy_so_callers_cannot_corrupt_the_ledger():
    # Arrange
    ctx = FakeToolContext()
    record(ctx, [fact("a", "A", 1, "unit", SOURCE_DATA)])

    # Act
    session_facts(ctx).clear()

    # Assert
    assert len(session_facts(ctx)) == 1


@pytest.mark.unit
def test_source_helpers_namespace_their_identifiers():
    assert source_evidence("ev_ndvi_kl_2025") == "evidence:ev_ndvi_kl_2025"
    assert source_assumption("cool_roof.albedo_cool") == "assumption:cool_roof.albedo_cool"
```

- [ ] **Step 2: Jalankan tes untuk memastikan gagal**

Run: `uv run pytest tests/test_facts.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'teduh_agent'`

- [ ] **Step 3: Tulis implementasi minimal**

Buat `teduh_agent/__init__.py` sebagai file kosong (M0-T4 mengisinya).

Buat `teduh_agent/facts.py`:

```python
"""Fact records: the only channel through which a number may reach the LLM.

CLAUDE.md rule 1 says Gemini never computes a figure, and rule 2 says every tool returns
`facts`. This module is the mechanism. A Fact binds a number to where it came from, and the
brief validator in teduh_agent/tools/brief.py rejects any figure in prose that has no
[[F:id]] marker pointing at one of these. That is the entire provenance guarantee, which is
why this module stays deliberately dumb: no rounding, no locale formatting, no domain logic.
Formatting belongs to the presentation layer, because a rounded number with a lost source is
exactly the failure this design exists to prevent.

The session ledger lives in ADK tool state so that get_session_facts() (M5) can hand the
policy_writer everything the conversation has already established.
"""

from typing import Any, TypedDict

Fact = TypedDict(
    "Fact",
    {"id": str, "label": str, "value": float | int | str, "unit": str, "source": str},
)

# Canonical source tokens. Anything else must go through source_evidence() or
# source_assumption() so the brief footnotes can resolve the citation.
SOURCE_DATA = "data:grid_features@v1"
SOURCE_MODEL = "model:lgbm@v1"

STATE_KEY = "facts"


def fact(id: str, label: str, value: float | int | str, unit: str, source: str) -> Fact:
    """Build one Fact.

    `id` must be stable across calls within a session: the policy brief references facts by
    id, so a drifting id silently breaks a citation rather than failing loudly.
    """
    if not id:
        raise ValueError("fact butuh id yang stabil, dapat kosong")
    if not source:
        raise ValueError(f"fact {id!r} butuh source (CLAUDE.md aturan 2), dapat kosong")
    return {"id": id, "label": label, "value": value, "unit": unit, "source": source}


def source_evidence(evidence_id: str) -> str:
    """Source token for a literature entry in data/evidence/interventions.json."""
    return f"evidence:{evidence_id}"


def source_assumption(key: str) -> str:
    """Source token for a config entry whose own `source` is "ASUMSI"."""
    return f"assumption:{key}"


def record(tool_context: Any, facts: list[Fact]) -> None:
    """Append facts to the session ledger, newest value winning on a duplicate id.

    A None context is a supported mode, not an error: api/routes.py calls the same tool
    functions over HTTP where there is no ADK session and therefore no ledger to keep.
    """
    if tool_context is None:
        return
    ledger: dict[str, Fact] = {f["id"]: f for f in tool_context.state.get(STATE_KEY, [])}
    ledger.update({f["id"]: f for f in facts})
    tool_context.state[STATE_KEY] = list(ledger.values())


def session_facts(tool_context: Any) -> list[Fact]:
    """Every fact recorded so far this session, as a copy the caller may not corrupt."""
    if tool_context is None:
        return []
    return list(tool_context.state.get(STATE_KEY, []))
```

- [ ] **Step 4: Jalankan tes untuk memastikan lulus**

Run: `uv run pytest tests/test_facts.py -v`
Expected: PASS, 8 tes.

- [ ] **Step 5: Commit**

```bash
git add teduh_agent/__init__.py teduh_agent/facts.py tests/test_facts.py
git commit -m "feat: tambah tipe Fact dan ledger fakta per sesi

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task M0-T3: Store artefak dan pembaca config

**Files:**
- Create: `teduh_agent/store.py`
- Create: `tests/conftest.py`
- Test: `tests/test_store.py`

**Interfaces:**
- Consumes: tidak ada (store tidak mengimpor facts).
- Produces:
  - `Store` — frozen dataclass: `kelurahan: pd.DataFrame` (index `kel_id`), `grid: pd.DataFrame` (index `cell_id`), `boundaries: dict`, `scenario_cfg: dict`, `costs_cfg: dict`, `hvi_cfg: dict`, `evidence: list[dict]`, `city_lst_mean: float`, `booster: Any | None`, `shap_by_kel: pd.DataFrame | None`, `model_card: dict | None`
  - `CITY_LST_FALLBACK = 41.8376`, `GOOD_QUALITY = "good"`
  - `load(*, data_root: Path | None = None, kelurahan_path: Path | None = None, grid_path: Path | None = None) -> Store`
  - `get_store() -> Store` — `lru_cache(maxsize=1)`
  - `config_entry(cfg: dict, *path: str) -> tuple[Any, str]`
  - `good_cells(grid: pd.DataFrame) -> pd.DataFrame`
- Fixture pytest yang dipakai semua milestone: `fixture_store` (3 kelurahan), `real_store` (264 kelurahan, di-skip kalau artefak tidak ada).

- [ ] **Step 1: Tulis tes yang gagal**

Buat `tests/conftest.py`:

```python
"""Shared fixtures. `fixture_store` is the default for unit tests: 3 kelurahan and 173 cells,
built by pipeline/make_fixtures.py with a deliberate spread in canopy and HVI so that
sign-direction assertions actually have something to bite on.

`real_store` is for integration checks and skips cleanly, because
data/processed/grid_features.parquet is gitignored (7 MB) and will be absent on a fresh clone.
"""

from pathlib import Path

import pytest

from teduh_agent import store as store_module

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
REAL_GRID = ROOT / "data" / "processed" / "grid_features.parquet"


@pytest.fixture(scope="session")
def fixture_store() -> store_module.Store:
    return store_module.load(
        kelurahan_path=FIXTURES / "kelurahan_metrics_sample.parquet",
        grid_path=FIXTURES / "grid_features_sample.parquet",
    )


@pytest.fixture(scope="session")
def real_store() -> store_module.Store:
    if not REAL_GRID.exists():
        pytest.skip(
            "data/processed/grid_features.parquet tidak ada (gitignored). "
            "Jalankan: uv run python -m pipeline.build_grid"
        )
    return store_module.load()
```

Buat `tests/test_store.py`:

```python
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
    assert len(fixture_store.evidence) == 10
    for entry in fixture_store.evidence:
        assert entry["id"]
        assert entry["intervention"]
        assert entry["metric"]
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
```

- [ ] **Step 2: Jalankan tes untuk memastikan gagal**

Run: `uv run pytest tests/test_store.py -v`
Expected: FAIL — `ImportError: cannot import name 'config_entry' from 'teduh_agent.store'`

- [ ] **Step 3: Tulis implementasi minimal**

Buat `teduh_agent/store.py`:

```python
"""One process-wide load of every artifact the runtime needs (CONCEPT §6.2 principle 3).

Earth Engine is never touched at request time; the app reads what pipeline/ already wrote.
Cloud Run pays one cold load of roughly 9 MB and then answers from memory, which is what
keeps p50 chat latency under the 8 s target. lru_cache makes that a singleton.

Model artifacts are optional by design. api/ and teduh_agent/tools/ must import cleanly
before model/train.py has ever been run, so booster, shap_by_kel and model_card stay None
until those files exist -- callers check and degrade rather than crash at import time.

Artifacts are baked into the container image rather than fetched from GCS at startup; see
docs/DECISIONS.md. TEDUH_DATA_DIR overrides the root for tests and for an image that mounts
data elsewhere.
"""

import json
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import lightgbm as lgb
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]

# Mean LST over good cells on the 2026-10-09 grid. Used only when the grid is absent, so a
# profile request can still state the city baseline instead of returning NaN.
CITY_LST_FALLBACK = 41.8376

GOOD_QUALITY = "good"


@dataclass(frozen=True)
class Store:
    """Every artifact the runtime reads, loaded once.

    kelurahan: one row per kelurahan, indexed by kel_id (264 on real data).
    grid: one row per 100 m cell, indexed by cell_id (75_636 on real data).
    """

    kelurahan: pd.DataFrame
    grid: pd.DataFrame
    boundaries: dict
    scenario_cfg: dict
    costs_cfg: dict
    hvi_cfg: dict
    evidence: list[dict]
    city_lst_mean: float
    booster: Any | None = None
    shap_by_kel: pd.DataFrame | None = None
    model_card: dict | None = None


def _data_root(override: Path | None = None) -> Path:
    if override is not None:
        return Path(override).resolve()
    env = os.environ.get("TEDUH_DATA_DIR")
    return Path(env).resolve() if env else ROOT


def _read_yaml(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"config wajib {path} tidak ada")
    return yaml.safe_load(path.read_text())


def good_cells(grid: pd.DataFrame) -> pd.DataFrame:
    """Cells with enough clean observations to trust thermally (DECISIONS 2026-10-09).

    Low-quality cells stay on the map and keep their residents, but they are excluded from
    every thermal statistic and from model training.
    """
    return grid[grid["lst_quality"] == GOOD_QUALITY]


def config_entry(cfg: dict, *path: str) -> tuple[Any, str]:
    """Read one config constant as (value, source).

    Enforces CLAUDE.md rule 4 at read time: an entry without a `source` raises instead of
    quietly becoming an unattributed number in a policy brief.
    """
    node: Any = cfg
    for key in path:
        if not isinstance(node, dict) or key not in node:
            raise KeyError(f"config path {'.'.join(path)} tidak ada")
        node = node[key]
    if not isinstance(node, dict) or "value" not in node:
        raise KeyError(f"config entry {'.'.join(path)} tidak punya value")
    if "source" not in node:
        raise KeyError(f"config entry {'.'.join(path)} tidak punya source (CLAUDE.md aturan 4)")
    return node["value"], node["source"]


def _load_booster(path: Path) -> Any | None:
    return lgb.Booster(model_file=str(path)) if path.exists() else None


def _load_parquet(path: Path, index: str) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(
            f"artefak {path} tidak ada. Jalankan pipeline dulu: "
            "uv run python -m pipeline.build_grid && "
            "uv run python -m pipeline.aggregate_kelurahan"
        )
    return pd.read_parquet(path).set_index(index)


def load(
    *,
    data_root: Path | None = None,
    kelurahan_path: Path | None = None,
    grid_path: Path | None = None,
) -> Store:
    """Load every artifact. Explicit paths let tests swap in the small fixtures."""
    root = _data_root(data_root)
    processed = root / "data" / "processed"
    model_dir = root / "data" / "model"

    kelurahan = _load_parquet(kelurahan_path or processed / "kelurahan_metrics.parquet", "kel_id")
    grid = _load_parquet(grid_path or processed / "grid_features.parquet", "cell_id")

    boundaries = json.loads((root / "data" / "boundaries" / "kelurahan.geojson").read_text())
    evidence_doc = json.loads((root / "data" / "evidence" / "interventions.json").read_text())

    city_mean = good_cells(grid)["lst_c"].mean()
    shap_path = model_dir / "shap_by_kel.parquet"
    card_path = model_dir / "model_card.json"

    return Store(
        kelurahan=kelurahan,
        grid=grid,
        boundaries=boundaries,
        scenario_cfg=_read_yaml(root / "config" / "scenario.yaml"),
        costs_cfg=_read_yaml(root / "config" / "costs.yaml"),
        hvi_cfg=_read_yaml(root / "config" / "hvi.yaml"),
        evidence=evidence_doc["evidence"],
        city_lst_mean=float(city_mean) if pd.notna(city_mean) else CITY_LST_FALLBACK,
        booster=_load_booster(model_dir / "model.txt"),
        shap_by_kel=pd.read_parquet(shap_path) if shap_path.exists() else None,
        model_card=json.loads(card_path.read_text()) if card_path.exists() else None,
    )


@lru_cache(maxsize=1)
def get_store() -> Store:
    """Process-wide singleton. Call this from tools and routes, never load() directly."""
    return load()
```

- [ ] **Step 4: Jalankan tes untuk memastikan lulus**

Run: `uv run pytest tests/test_store.py -v`
Expected: PASS, 12 tes (yang terakhir di-skip kalau `grid_features.parquet` tidak ada).

- [ ] **Step 5: Commit**

```bash
git add teduh_agent/store.py tests/conftest.py tests/test_store.py
git commit -m "feat: tambah store artefak tunggal dan pembaca config berbasis source

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task M0-T4: Agen ADK dengan satu tool nyata

**Files:**
- Create: `teduh_agent/agent.py`
- Modify: `teduh_agent/__init__.py` (dari kosong menjadi `from . import agent`)
- Test: `tests/test_agent_smoke.py`

**Interfaces:**
- Consumes: `teduh_agent.store.get_store`, `teduh_agent.facts.fact`, `teduh_agent.facts.record`, `teduh_agent.facts.SOURCE_DATA`.
- Produces:
  - `MODEL: str` — dibaca dari env `TEDUH_MODEL`
  - `INSTRUCTION: str`
  - `root_agent: LlmAgent` dengan `name="teduh_coordinator"`
  - `count_kelurahan(tool_context: ToolContext) -> dict` — tool contoh, **dihapus di M4**

**Catatan tentang bahasa docstring:** docstring tool adalah **materi prompt** yang dibaca Gemini untuk memilih tool, bukan komentar kode. Karena pengguna bertanya dalam Bahasa Indonesia, docstring tool ditulis **Bahasa Indonesia** agar pencocokannya kuat. Komentar `#` dan nama variabel tetap Inggris sesuai CLAUDE.md aturan 7.

- [ ] **Step 1: Tulis tes yang gagal**

Buat `tests/test_agent_smoke.py`:

```python
"""Smoke test only: proves the ADK agent is wired and its tool returns facts, without
calling Gemini. Routing quality is measured by tests/eval/run_golden.py in M8."""

import importlib

import pytest

import teduh_agent.agent as agent_module
from teduh_agent.agent import count_kelurahan, root_agent


class FakeToolContext:
    def __init__(self) -> None:
        self.state: dict = {}


@pytest.mark.unit
def test_root_agent_is_named_teduh_coordinator():
    # tests/eval/golden_questions.yaml matches on agent names, so this is a contract.
    assert root_agent.name == "teduh_coordinator"


@pytest.mark.unit
def test_root_agent_model_comes_from_the_environment(monkeypatch):
    monkeypatch.setenv("TEDUH_MODEL", "gemini-test-model")
    try:
        reloaded = importlib.reload(agent_module)
        assert reloaded.MODEL == "gemini-test-model"
    finally:
        monkeypatch.delenv("TEDUH_MODEL", raising=False)
        importlib.reload(agent_module)


@pytest.mark.integration
def test_count_kelurahan_returns_a_fact_with_a_data_source():
    # Arrange
    ctx = FakeToolContext()

    # Act
    result = count_kelurahan(ctx)

    # Assert
    assert result["facts"], "tool wajib mengembalikan facts (CLAUDE.md aturan 2)"
    only = result["facts"][0]
    assert only["source"] == "data:grid_features@v1"
    assert only["value"] == 264
    assert only["unit"] == "kelurahan"


@pytest.mark.integration
def test_count_kelurahan_records_its_fact_in_the_session_ledger():
    # Arrange
    ctx = FakeToolContext()

    # Act
    count_kelurahan(ctx)

    # Assert
    assert ctx.state["facts"][0]["id"] == "data.kelurahan_count"
```

Dua tes `integration` memakai artefak nyata (264 kelurahan). Kalau `grid_features.parquet` tidak ada, keduanya gagal dengan `FileNotFoundError` yang menyebutkan perintah pipeline — itu perilaku yang diinginkan.

- [ ] **Step 2: Jalankan tes untuk memastikan gagal**

Run: `uv run pytest tests/test_agent_smoke.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'teduh_agent.agent'`

- [ ] **Step 3: Tulis implementasi minimal**

Buat `teduh_agent/agent.py`:

```python
"""ADK entry point.

M0 ships exactly one tool so the whole deployment path -- uv sync, adk web, Docker image,
Cloud Run -- is proven before any domain logic lands. M4 replaces this single agent with
teduh_coordinator plus four sub-agents; the tool contract does not change, which is what
makes deferring that swap safe.

Tool docstrings are written in Indonesian on purpose: ADK feeds them to Gemini as the tool
description, and users ask in Indonesian, so Indonesian descriptions match more reliably.
Code comments and identifiers stay English per CLAUDE.md rule 7.
"""

import os

from google.adk.agents import LlmAgent
from google.adk.tools import ToolContext

from .facts import SOURCE_DATA, fact, record
from .store import get_store

# Never hard-code a model id: the Gemini Flash generation moves, and CONCEPT §11.1 requires
# this to be swappable without a code change.
MODEL = os.environ.get("TEDUH_MODEL", "gemini-3.8-flash")

INSTRUCTION = """\
Kamu adalah TEDUH, asisten perencanaan mitigasi panas perkotaan untuk pemerintah daerah
di Indonesia.

Aturan yang tidak boleh dilanggar:
- Jawab dalam Bahasa Indonesia yang jelas untuk pegawai pemerintah daerah, kecuali
  pengguna memakai bahasa lain.
- JANGAN PERNAH menulis angka yang tidak berasal dari hasil tool. Kalau datanya tidak ada,
  katakan tidak ada.
- Sebut sumber angka ketika relevan.
"""


def count_kelurahan(tool_context: ToolContext) -> dict:
    """Hitung jumlah kelurahan yang tersedia dalam data TEDUH.

    Gunakan tool ini kalau pengguna bertanya berapa banyak kelurahan yang dicakup TEDUH
    atau seberapa luas cakupan datanya.

    Returns:
        dict dengan kunci `facts`: daftar fakta berisi jumlah kelurahan beserta sumbernya.
    """
    store = get_store()
    facts = [
        fact(
            "data.kelurahan_count",
            "Jumlah kelurahan dalam data TEDUH",
            len(store.kelurahan),
            "kelurahan",
            SOURCE_DATA,
        )
    ]
    record(tool_context, facts)
    return {"facts": facts}


root_agent = LlmAgent(
    name="teduh_coordinator",
    model=MODEL,
    description="Koordinator TEDUH untuk analisis panas perkotaan tingkat kelurahan.",
    instruction=INSTRUCTION,
    tools=[count_kelurahan],
)
```

Ganti isi `teduh_agent/__init__.py` menjadi:

```python
"""TEDUH ADK agent package.

`from . import agent` is required: ADK discovers root_agent by importing the package.
"""

from . import agent

__all__ = ["agent"]
```

- [ ] **Step 4: Jalankan tes untuk memastikan lulus**

Run: `uv run pytest tests/test_agent_smoke.py -v`
Expected: PASS, 4 tes.

- [ ] **Step 5: Verifikasi agen jalan di UI dev ADK**

Run: `uv run adk web`
Expected: server naik; di browser pilih agen `teduh_agent`, tanya "Berapa kelurahan yang dicakup TEDUH?", jawabannya menyebut **264** dan `count_kelurahan` terlihat terpanggil di panel event.

Kalau ADK tidak menemukan agen, jalankan `adk web` dari root repo — ADK memindai subdirektori yang berisi paket dengan `root_agent`.

- [ ] **Step 6: Commit**

```bash
git add teduh_agent/agent.py teduh_agent/__init__.py tests/test_agent_smoke.py
git commit -m "feat: tambah root_agent ADK dengan satu tool berbasis facts

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task M0-T5: Image container

**Files:**
- Create: `infra/Dockerfile`
- Create: `infra/cloudbuild.yaml`
- Create: `.dockerignore`
- Create: `api/__init__.py` (placeholder, agar `COPY api/` tidak gagal; M3-T7 mengisi paketnya)
- Modify: `docs/DECISIONS.md` (tambah satu entri sebelum baris penutup "Rincian semua sumber")

**Interfaces:**
- Consumes: `pyproject.toml` + `uv.lock` (M0-T1), paket `teduh_agent` (M0-T4).
- Produces: image yang bisa dibangun dengan `docker build -f infra/Dockerfile .`; `infra/cloudbuild.yaml` dengan substitusi `_IMAGE` yang dipakai `deploy_api.sh` (M0-T6).

- [ ] **Step 1: Tulis `.dockerignore`**

```gitignore
.git
.venv
__pycache__
*.pyc
.ruff_cache
.pytest_cache
.DS_Store
web/node_modules
web/.next
data/raw
data/roof_test/photos
docs
design
tests
*.pdf
.env
```

`data/raw` dikecualikan karena berisi raster dan PDF 11 MB yang hanya dipakai `pipeline/` offline.

- [ ] **Step 2: Buat placeholder paket `api`**

`COPY api/ api/` akan gagal sampai M3-T7 membuat direktori itu, jadi buat placeholder sekarang:

```bash
mkdir -p api
cat > api/__init__.py <<'EOF'
"""FastAPI layer. Routes land in M3; this placeholder exists so the container image can be
built and the deployment path proven before the API has any endpoints."""
EOF
```

- [ ] **Step 3: Tulis `infra/Dockerfile`**

```dockerfile
# TEDUH API image.
#
# Data artifacts are COPYed into the image rather than fetched from GCS at startup. They
# total about 9 MB, which is far too small to justify a network dependency plus credentials
# plus download-failure handling on the critical path during judging. See docs/DECISIONS.md.
#
# WeasyPrint renders the policy brief PDF and needs Pango/Cairo as system libraries; pip
# cannot supply those, which is why this is a slim image with apt packages and not distroless.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
        libcairo2 \
        libgdk-pixbuf-2.0-0 \
        libffi8 \
        shared-mime-info \
        fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /usr/local/bin/uv

WORKDIR /app

# Dependencies first so a code change does not invalidate the dependency layer.
# --no-group pipeline keeps earthengine-api, rasterio and geopandas out of the runtime
# image (CLAUDE.md rule 6): Earth Engine is never called at request time.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-group pipeline

COPY teduh_agent/ teduh_agent/
COPY model/ model/
COPY api/ api/
COPY config/ config/
COPY data/boundaries/ data/boundaries/
COPY data/processed/ data/processed/
COPY data/evidence/ data/evidence/
COPY data/model/ data/model/

ENV PATH="/app/.venv/bin:$PATH" \
    PORT=8080

EXPOSE 8080

# Cloud Run injects PORT, so it is expanded at runtime by the shell rather than baked in.
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT}"]
```

- [ ] **Step 4: Tulis `infra/cloudbuild.yaml`**

Dockerfile ada di `infra/`, bukan di root, sehingga `gcloud builds submit --tag` tidak bisa dipakai langsung. Konfigurasi eksplisit ini memakai `-f`.

```yaml
# Build the API image with the Dockerfile in infra/ against the repo root as context.
steps:
  - name: gcr.io/cloud-builders/docker
    args: ["build", "-f", "infra/Dockerfile", "-t", "${_IMAGE}", "."]
images: ["${_IMAGE}"]
options:
  logging: CLOUD_LOGGING_ONLY
```

- [ ] **Step 5: Verifikasi image bisa dibangun dan memuat store**

Run: `docker build -f infra/Dockerfile -t teduh-api:dev .`
Expected: build sukses.

Run: `docker run --rm teduh-api:dev python -c "from teduh_agent.agent import root_agent; print(root_agent.name)"`
Expected: `teduh_coordinator`

Run: `docker run --rm teduh-api:dev python -c "from teduh_agent.store import get_store; print(len(get_store().kelurahan))"`
Expected: `264`

Catatan: `CMD` image menjalankan `uvicorn api.main:app`, yang baru ada setelah M3-T9. Sampai saat itu jalankan container dengan perintah eksplisit seperti di atas, jangan `docker run teduh-api:dev` tanpa argumen.

- [ ] **Step 6: Catat keputusan di `docs/DECISIONS.md`**

Tambahkan entri ini **sebelum** baris terakhir (`Rincian semua sumber: docs/DATA_SOURCES.md.`):

```markdown
## 2026-10-09 — Artefak data dibakar ke image Docker, bukan diunduh dari GCS

- **Konsep (§11.1):** `TEDUH_DATA_URI=gs://<bucket>/teduh/v1/`, artefak diunduh saat startup.
- **Keputusan:** `infra/Dockerfile` mem-`COPY` `data/{boundaries,processed,evidence,model}` ke dalam image. Env `TEDUH_DATA_DIR` disediakan untuk menunjuk direktori lain (dipakai tes).
- **Alasan:** total artefak ~9,3 MB (`grid_features.parquet` 7,0 MB + `kelurahan.geojson` 2,2 MB + sisanya 96 KB). Jalur GCS menambah kredensial, kuota, dan penanganan gagal-unduh ke jalur kritis tepat saat penilaian, hanya untuk menghemat 9 MB ukuran image. Membakar artefak menghapus satu titik gagal dan membuat image bisa direproduksi apa adanya.
- **Risiko:** setiap pembaruan data butuh build image baru. Dapat diterima karena pipeline offline hanya dijalankan ulang saat sumber data berubah. Kalau artefak tumbuh melewati ~100 MB, kembali ke jalur GCS dan catat di sini.
```

- [ ] **Step 7: Commit**

```bash
git add infra/Dockerfile infra/cloudbuild.yaml .dockerignore api/__init__.py docs/DECISIONS.md
git commit -m "chore: tambah image container dengan artefak data dibakar ke dalam image

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task M0-T6: Skrip deploy Cloud Run

**Files:**
- Create: `infra/deploy_api.sh` (mode `755`)
- Modify: `CLAUDE.md` — bagian "Perintah (isi/rapikan setelah M0)"

**Interfaces:**
- Consumes: `infra/Dockerfile` dan `infra/cloudbuild.yaml` (M0-T5); env `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION`, `TEDUH_MODEL`, `TEDUH_MIN_INSTANCES`.
- Produces: layanan Cloud Run `teduh-api` dengan URL publik; skrip mencetak URL itu di akhir.

- [ ] **Step 1: Tulis `infra/deploy_api.sh`**

```bash
#!/usr/bin/env bash
# Build and deploy teduh-api to Cloud Run.
#
# Fails fast when a data artifact is missing, because the image bakes artifacts in
# (docs/DECISIONS.md) and a deploy that silently ships an image without grid_features would
# only surface as a 500 during judging.
set -euo pipefail

PROJECT="${GOOGLE_CLOUD_PROJECT:?GOOGLE_CLOUD_PROJECT belum diisi}"
REGION="${GOOGLE_CLOUD_LOCATION:-asia-southeast2}"
SERVICE="teduh-api"
REPO="teduh"
MIN_INSTANCES="${TEDUH_MIN_INSTANCES:-0}"
MODEL="${TEDUH_MODEL:-gemini-3.8-flash}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

REQUIRED_ARTIFACTS=(
  "data/processed/kelurahan_metrics.parquet"
  "data/processed/grid_features.parquet"
  "data/boundaries/kelurahan.geojson"
  "data/evidence/interventions.json"
  "config/scenario.yaml"
  "config/costs.yaml"
  "config/hvi.yaml"
)

for artifact in "${REQUIRED_ARTIFACTS[@]}"; do
  if [[ ! -f "$artifact" ]]; then
    echo "GAGAL: $artifact tidak ada." >&2
    echo "Jalankan dulu: uv run python -m pipeline.build_grid && uv run python -m pipeline.aggregate_kelurahan" >&2
    exit 1
  fi
done

if [[ ! -f "data/model/model.txt" ]]; then
  echo "PERINGATAN: data/model/model.txt tidak ada. Tool skenario akan menolak melayani." >&2
  echo "Jalankan: uv run python -m model.train" >&2
fi

IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/${REPO}/${SERVICE}:$(date +%Y%m%d-%H%M%S)"

# Idempotent: succeeds quietly when the repository already exists.
gcloud artifacts repositories create "$REPO" \
  --project "$PROJECT" --location "$REGION" --repository-format docker \
  --description "TEDUH container images" 2>/dev/null || true

echo "==> build $IMAGE"
gcloud builds submit "$ROOT" \
  --project "$PROJECT" \
  --config infra/cloudbuild.yaml \
  --substitutions "_IMAGE=${IMAGE}"

echo "==> deploy $SERVICE ke $REGION"
gcloud run deploy "$SERVICE" \
  --project "$PROJECT" \
  --region "$REGION" \
  --image "$IMAGE" \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --timeout 300 \
  --concurrency 20 \
  --min-instances "$MIN_INSTANCES" \
  --max-instances 4 \
  --set-env-vars "GOOGLE_CLOUD_PROJECT=${PROJECT},GOOGLE_CLOUD_LOCATION=${REGION},GOOGLE_GENAI_USE_ENTERPRISE=True,TEDUH_MODEL=${MODEL}"

URL="$(gcloud run services describe "$SERVICE" --project "$PROJECT" --region "$REGION" --format 'value(status.url)')"
echo "==> selesai: $URL"
```

`--memory 2Gi` dipilih karena grid 75.636 baris × 24 kolom plus booster LightGBM dan SHAP explainer semuanya tinggal di memori; 512 Mi tidak cukup. `--concurrency 20` menjaga satu instance tidak melayani terlalu banyak permintaan SHAP bersamaan.

- [ ] **Step 2: Jadikan skrip bisa dieksekusi dan verifikasi guard-nya**

```bash
chmod +x infra/deploy_api.sh
```

Run: `env -u GOOGLE_CLOUD_PROJECT ./infra/deploy_api.sh`
Expected: keluar dengan kode bukan nol dan pesan `GOOGLE_CLOUD_PROJECT belum diisi` — membuktikan skrip gagal cepat, bukan diam-diam deploy ke proyek yang salah.

- [ ] **Step 3: Rapikan bagian Perintah di `CLAUDE.md`**

Ganti baris judul `## Perintah (isi/rapikan setelah M0)` menjadi `## Perintah`, lalu pastikan blok di bawahnya berisi tepat ini:

```bash
uv sync                                   # install
uv run pytest -q                          # tes
uv run adk web                            # UI dev ADK lokal
uv run uvicorn api.main:app --reload      # API lokal
uv run python -m pipeline.gee_extract     # pipeline offline (butuh akses Earth Engine)
uv run python -m model.train              # latih model
cd web && npm run dev                     # frontend
./infra/deploy_api.sh                     # deploy Cloud Run
```

- [ ] **Step 4: Jalankan seluruh suite tes**

Run: `uv run pytest -q`
Expected: PASS semua (24 tes dari M0-T2 sampai M0-T4; satu di-skip kalau `grid_features.parquet` tidak ada).

- [ ] **Step 5: Commit**

```bash
git add infra/deploy_api.sh CLAUDE.md
git commit -m "chore: tambah skrip deploy Cloud Run dengan guard artefak

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Definisi M0 selesai

- [ ] `uv sync` bersih; `uv run pytest -q` hijau.
- [ ] `uv run adk web` menjawab "Berapa kelurahan yang dicakup TEDUH?" dengan **264** lewat tool `count_kelurahan`.
- [ ] `docker build -f infra/Dockerfile .` sukses dan container bisa memuat store (264 kelurahan).
- [ ] `./infra/deploy_api.sh` gagal cepat tanpa `GOOGLE_CLOUD_PROJECT`. Deploy sebenarnya boleh ditunda sampai M3 ketika `api/main.py` sudah ada, karena `CMD` image menjalankan uvicorn.
- [ ] Keputusan "artefak dibakar ke image" tercatat di `docs/DECISIONS.md`.
- [ ] Tidak ada kredensial ter-commit; `.env` ada di `.gitignore`.

**Selanjutnya:** [`m2-model.md`](m2-model.md) — `model/hvi.py`, `model/train.py`, `model/explain.py`.
