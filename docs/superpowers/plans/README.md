# TEDUH — Indeks Rencana Implementasi

> **Untuk pekerja agentik:** REQUIRED SUB-SKILL: pakai `superpowers:subagent-driven-development` (disarankan) atau `superpowers:executing-plans` untuk mengerjakan rencana ini task demi task. Semua langkah memakai checkbox (`- [ ]`).

**Cara memakai dokumen ini:** buka file rencana milestone yang mau dikerjakan. Setiap file berdiri sendiri — satu chat baru cukup membaca **file ini** (untuk Global Constraints + Interface Registry) lalu **satu file milestone**. Jangan baca semuanya sekaligus.

**Tujuan:** mengubah data panas Jakarta yang sudah ada di disk menjadi agen ADK + API + web yang bisa didemokan, di mana setiap angka bisa ditelusuri ke data, model, literatur, atau asumsi berlabel.

**Dokumen rujukan:** `docs/CONCEPT.md` (desain) · `docs/DECISIONS.md` (penyimpangan) · `docs/PRD.md` (persyaratan) · `design/README.md` (handoff UI hi-fi) · `CLAUDE.md` (aturan wajib).

---

## Status: apa yang sudah ada

**M1 (data) SUDAH SELESAI.** Jangan bangun ulang. Yang ada di disk:

```
config/{scenario,costs,hvi}.yaml          konstanta berlabel source/ASUMSI
data/boundaries/kelurahan.geojson         264 MultiPolygon CRS84
data/processed/grid_features.parquet      75.636 sel x 24 kolom (gitignored, 7 MB)
data/processed/kelurahan_metrics.parquet  264 kelurahan x 32 kolom (committed)
data/evidence/interventions.json          10 entri bukti, semua verified
pipeline/*.py                             10 skrip offline (GEE, grid, agregasi, BMKG, biaya)
tests/fixtures/*.parquet                  3 kelurahan x 173 sel
tests/eval/golden_questions.yaml          20 pertanyaan
design/                                   handoff UI hi-fi + token final
```

**Belum ada sama sekali:** `pyproject.toml`, `model/`, `teduh_agent/`, `api/`, `web/`, `infra/`, dan semua `tests/test_*.py`.

## Daftar rencana

| Milestone | File | Isi | Tergantung pada |
|---|---|---|---|
| **M0** Kerangka | [`m0-skeleton.md`](m0-skeleton.md) | `pyproject.toml`, store artefak, helper facts, agen "hello tool", Dockerfile, deploy script | — |
| **M2** Model | [`m2-model.md`](m2-model.md) | `model/hvi.py`, `train.py`, `explain.py`, `model_card.json` | M0 |
| **M3a** Mesin skenario | [`m3-scenario-engine.md`](m3-scenario-engine.md) | `model/scenario.py`, `model/costs.py` | M0, M2 |
| **M3b** Tools | [`m3-tools.md`](m3-tools.md) | 7 tool deterministik, termasuk optimizer CP-SAT | M3a |
| **M3c** REST API | [`m3-api.md`](m3-api.md) | skema Pydantic, router `/api/*`, perakitan app ADK | M3b |
| **M4** Agen | [`m4-agent.md`](m4-agent.md) | prompt sistem, 4 sub-agen, root agent, fallback satu agen | M3 |
| **M5** Brief | [`m5-brief.md`](m5-brief.md) | validator provenance, render Markdown→PDF, endpoint brief | M3 |
| **M6** Cek Atap | [`m6-roof.md`](m6-roof.md) | Gemini vision terstruktur, aturan rekomendasi, endpoint foto | M3 |
| **M7a** Fondasi frontend | [`m7a-web-foundation.md`](m7a-web-foundation.md) | kerangka Next.js, token desain, format angka, lapisan peta, `SourceChip`, header | M3c (API hidup) |
| **M7b** Fitur frontend | [`m7b-web-features.md`](m7b-web-features.md) | peta, overlay, drawer, dok skenario, panel agen SSE, `/cek-atap`, `/sumber-data` | M7a, M4, M6 |
| **M8** Evaluasi & deploy | [`m8-eval-deploy.md`](m8-eval-deploy.md) | runner golden questions, evaluasi atap, deploy Cloud Run + Firebase | semua |

Urutan kerja minimum untuk demo: **M0 → M2 → M3 → M4 → M5 → M7 → M8**. M6 bisa dikerjakan paralel setelah M3.

---

## Global Constraints

Berlaku untuk **setiap** task di semua file rencana. Nilai dikutip apa adanya dari spesifikasi.

### Aturan wajib (`CLAUDE.md`)
1. **LLM tidak menghitung angka.** Semua angka dari fungsi Python deterministik di `teduh_agent/tools/` atau `model/`. Gemini hanya memilih tool dan menulis narasi.
2. **Setiap tool mengembalikan `facts`** dengan `id`, `label`, `value`, `unit`, `source`. Jangan buat tool yang mengembalikan angka tanpa `facts`.
3. **Brief wajib lolos validator provenance.** Jangan melemahkan validator agar tes lulus.
4. **Jangan mengarang konstanta.** Harga, albedo, NDVI target hanya di `config/*.yaml`, setiap entri wajib punya `source:` (sitasi atau `"ASUMSI"`).
5. **Model ML:** LightGBM dengan monotonic constraints, spatial block CV. Jangan pakai lat/lon sebagai fitur. Jangan melaporkan metrik dari random split.
6. **Earth Engine tidak dipanggil saat runtime.** Hanya di `pipeline/` (offline).
7. Teks UI dan jawaban agen: **Bahasa Indonesia**, toggle Inggris. Kode, nama variabel, dan komentar: **Inggris**.
8. Jangan commit kredensial, data mentah besar, atau foto pengguna.

### Versi dan dependensi
- Python **3.12**, manajer paket **`uv`**.
- Paket: `google-adk`, `google-genai`, `fastapi`, `lightgbm`, `shap`, `scikit-learn`, `ortools`, `geopandas`, `pyarrow`, `pandas`, `numpy`, `pyyaml`, `weasyprint`. `earthengine-api` **hanya** di grup `pipeline`.
- Frontend: Next.js App Router + TypeScript + Tailwind + MapLibre GL JS, di `web/`.
- Model Gemini dibaca dari env **`TEDUH_MODEL`** (default `gemini-3.8-flash`). **Jangan hard-code model ID.**
- Paket agen ADK di `teduh_agent/` dengan `root_agent` di `agent.py` dan `from . import agent` di `__init__.py`.

### Angka acuan nyata (pakai ini, bukan contoh di `design/README.md`)
- **264** kelurahan, **75.636** sel grid, **75.608** `lst_quality == "good"`, **28** `"low"`.
- Rata-rata LST kota = **41,8376 °C** (dihitung dari sel `good`).
- Kode kota: `ID3171` Jakarta Selatan · `ID3172` Jakarta Timur · `ID3173` Jakarta Pusat · `ID3174` Jakarta Barat · `ID3175` Jakarta Utara.
- Format `kel_id`: `ID3173040002` (12 karakter). `kec_id`: `ID3173040`. `kota_id`: `ID3173`.
- 5 kelurahan HVI teratas: Kampung Rawa `ID3173040002` (0,9309) · Serdang `ID3173060004` (0,8987) · Johar Baru `ID3173040001` (0,8358) · Galur `ID3173040004` (0,8185) · Krendang `ID3174050005` (0,8063).
- **NaN yang nyata ada dan harus ditangani:** di sel `good`, `lst_c` punya 5 NaN dan `pop` punya 1.207 NaN. Jangan asumsikan kolom bersih.

### Gaya kode
- Ikuti pola `pipeline/*.py` yang sudah ada: docstring modul yang menjelaskan **kenapa**, konstanta `UPPER_SNAKE` di atas, `main()`, lalu `check()` yang meng-`assert` invarian dan mencetak ringkasan. Dijalankan lewat `python -m <paket>.<modul>`.
- Type annotation di semua signature. `@dataclass(frozen=True)` untuk DTO. Jangan mutasi input — kembalikan salinan baru.
- File 200–400 baris tipikal, maksimal 800. Fungsi < 50 baris. Nesting maksimal 4 level.
- Pesan `print()` dan teks yang dilihat pengguna: Bahasa Indonesia. Identifier dan komentar: Inggris.

### Perintah
```bash
uv sync                                   # install
uv run pytest -q                          # tes
uv run adk web                            # UI dev ADK lokal
uv run uvicorn api.main:app --reload      # API lokal
uv run python -m model.train              # latih model
cd web && npm run dev                     # frontend
./infra/deploy_api.sh                     # deploy Cloud Run
```

### Git
- Conventional commits: `<type>: <description>`, type dari `feat, fix, refactor, docs, test, chore, perf, ci`.
- Repo **belum** di-`git init`. Task M0-T1 yang melakukannya.
- Akhiri commit message dengan `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`.

---

## Interface Registry

Kontrak lintas-task. **Ini yang membuat satu chat baru bisa mengerjakan satu milestone tanpa membaca milestone lain.** Kalau sebuah task butuh nama atau tipe dari task lain, cari di sini.

### `teduh_agent/facts.py` (M0-T3)
```python
Fact = TypedDict("Fact", {"id": str, "label": str,
                          "value": float | int | str, "unit": str, "source": str})

SOURCE_DATA  = "data:grid_features@v1"
SOURCE_MODEL = "model:lgbm@v1"

def fact(id: str, label: str, value, unit: str, source: str) -> Fact
def source_evidence(evidence_id: str) -> str      # -> "evidence:ev_ndvi_kl_2025"
def source_assumption(key: str) -> str            # -> "assumption:cool_roof.albedo_cool"
def record(tool_context, facts: list[Fact]) -> None   # append ke state["facts"], dedupe by id
def session_facts(tool_context) -> list[Fact]
```

### `teduh_agent/store.py` (M0-T2)
```python
@dataclass(frozen=True)
class Store:
    kelurahan: pd.DataFrame        # kelurahan_metrics.parquet, index = kel_id
    grid: pd.DataFrame             # grid_features.parquet, index = cell_id
    boundaries: dict               # GeoJSON FeatureCollection
    scenario_cfg: dict
    costs_cfg: dict
    hvi_cfg: dict
    evidence: list[dict]           # isi key "evidence" dari interventions.json
    booster: "lgb.Booster | None"  # None sebelum M2 selesai
    shap_by_kel: pd.DataFrame | None
    model_card: dict | None
    city_lst_mean: float           # 41.8376 pada data sekarang

CITY_LST_FALLBACK = 41.8376

def get_store() -> Store                              # lru_cache(maxsize=1)
def config_entry(cfg: dict, *path: str) -> tuple[object, str]   # -> (value, source)
def good_cells(grid: pd.DataFrame) -> pd.DataFrame    # grid[grid.lst_quality == "good"]
```
`config_entry(costs_cfg, "cool_roof", "cost_idr_per_m2")` → `(95000, "ASUMSI")`.

### `model/hvi.py` (M2-T1)
```python
DEFAULT_WEIGHTS: dict[str, float] = {"wE": 0.4, "wS": 0.3, "wA": 0.3}

def percentile(series: pd.Series) -> pd.Series          # rank(pct=True, na_option="keep")
def load_weights(hvi_cfg: dict) -> dict[str, float]
def components(kel: pd.DataFrame) -> pd.DataFrame       # kolom H, E, S, A
def hvi(comp: pd.DataFrame, weights: dict[str, float]) -> pd.Series
def rank(hvi_series: pd.Series) -> pd.Series            # 1 = paling rentan, Int64
```

### `model/train.py` (M2-T2)
```python
FEATURES: list[str] = ["albedo", "ndvi", "ndbi", "ndwi", "tree_frac", "built_frac",
                       "water_frac", "roof_frac", "bldg_h_mean", "elev_m",
                       "dist_coast_km", "pop"]
TARGET = "lst_c"
MONOTONE: dict[str, int] = {"albedo": -1, "ndvi": -1, "tree_frac": -1, "water_frac": -1,
                            "built_frac": 1, "ndbi": 1}
BLOCK_M = 1000
N_FOLDS = 5
MODEL_PATH      = ROOT / "data" / "model" / "model.txt"
MODEL_CARD_PATH = ROOT / "data" / "model" / "model_card.json"

def monotone_constraints() -> list[int]                  # sejajar FEATURES
def spatial_blocks(frame: pd.DataFrame, block_m: int = BLOCK_M) -> pd.Series
def prepare(grid: pd.DataFrame) -> pd.DataFrame          # good cells, dropna lst_c, pop->0
def cross_validate(frame: pd.DataFrame) -> list[dict]    # per lipatan: r2, rmse, mae, n
def fit_final(frame: pd.DataFrame) -> "lgb.Booster"
def predict(booster, frame: pd.DataFrame) -> np.ndarray  # selalu frame[FEATURES]
```

### `model/explain.py` (M2-T3)
```python
SHAP_PATH = ROOT / "data" / "model" / "shap_by_kel.parquet"

def shap_values(booster, frame: pd.DataFrame) -> np.ndarray      # (n_rows, n_features)
def by_kelurahan(booster, frame: pd.DataFrame) -> pd.DataFrame
# kolom: kel_id, base_value, shap_<feature> untuk setiap FEATURES, pred_lst_c
```

### `model/scenario.py` (M3-T1)
```python
@dataclass(frozen=True)
class Intervention:
    type: str          # "tree_planting" | "cool_roof" | "green_roof"
    params: dict       # tree_planting: {"canopy_increase_pp": float}
                       # cool_roof/green_roof: {"adoption_rate": float}

LEVELS: dict[str, dict[str, float]] = {
    "tree_planting": {"low": 2.0,  "medium": 5.0,  "high": 10.0},   # canopy_increase_pp
    "cool_roof":     {"low": 0.25, "medium": 0.50, "high": 0.75},   # adoption_rate
    "green_roof":    {"low": 0.10, "medium": 0.20, "high": 0.35},
}

@dataclass(frozen=True)
class ScenarioResult:
    kel_id: str
    delta_lst_c: float               # rata-rata, negatif = mendingin
    delta_lst_pop_weighted_c: float
    vulnerable_benefiting: float     # jiwa di sel dengan delta <= -0.5
    area_m2: float
    area_by_type: dict[str, float]   # luas per jenis intervensi
    cost_idr: float
    cost_sources: tuple[str, ...]    # source tiap harga yang dipakai (CLAUDE.md aturan 4)
    extrapolation: bool
    extrapolated_features: tuple[str, ...]
    n_cells: int

PARAM_NAME: dict[str, str]           # {TREE: "canopy_increase_pp", COOL_ROOF/GREEN_ROOF: "adoption_rate"}
INTERVENTION_TYPES: tuple[str, str, str]
TREE, COOL_ROOF, GREEN_ROOF: str

def from_level(itype: str, level: str) -> Intervention
def plantable_headroom(cells: pd.DataFrame) -> pd.Series
def treated_fractions(cells: pd.DataFrame, interventions: list[Intervention],
                      scenario_cfg: dict) -> dict[str, pd.Series]   # sumber kebenaran luas
def apply_interventions(cells: pd.DataFrame, interventions: list[Intervention],
                        scenario_cfg: dict) -> pd.DataFrame     # salinan baru, FEATURES diubah
def intervened_area_m2(cells: pd.DataFrame, interventions: list[Intervention],
                       scenario_cfg: dict) -> dict[str, float]  # per tipe intervensi
def simulate(cells: pd.DataFrame, interventions: list[Intervention], booster,
             scenario_cfg: dict, costs_cfg: dict,
             train_q99: pd.Series) -> ScenarioResult
def training_quantiles(frame: pd.DataFrame, percentile: float | None = None) -> pd.Series
```

Catatan: `config/scenario.yaml` mendapat satu entri baru di M3a, `green_roof.ndvi_green` (0,35, `source: "ASUMSI"`).

### `model/costs.py` (M3-T2)
```python
CELL_AREA_M2 = 92.8 * 92.2     # 8_556.16, konsisten dengan pipeline/aggregate_kelurahan.py
COST_KEYS: dict[str, tuple[tuple[str, str], ...]]   # jenis -> entri config, urutan sitasi

def intervention_cost(itype: str, area_m2: float,
                      costs_cfg: dict) -> tuple[float, list[str]]   # (idr, daftar source)
def trees_for_area(area_m2: float, costs_cfg: dict) -> float
```

### Tool ADK — nama fungsi tetap, dipakai golden questions
`teduh_agent/tools/areas.py` (M3-T3): `find_area`, `get_area_profile`, `rank_priority_areas`, `explain_drivers`
`teduh_agent/tools/scenario_tools.py` (M3-T4): `simulate_intervention`
`teduh_agent/tools/optimize.py` (M3-T5): `optimize_portfolio`
`teduh_agent/tools/evidence.py` (M3-T6): `get_evidence`
`teduh_agent/tools/brief.py` (M5): `get_session_facts`, `render_policy_brief`
`teduh_agent/tools/roof.py` (M6): `analyze_roof_photo`, `recommend_roof_action`

Semua mengembalikan `dict` dengan minimal `facts: list[Fact]`, opsional `map_highlight: list[str]`, dan payload spesifik tool. **Nama ini tidak boleh diubah** — `tests/eval/golden_questions.yaml` mencocokkannya.

### Nama sub-agen — tetap, dipakai golden questions
`heat_analyst` · `intervention_planner` · `policy_writer` · `roof_inspector` · root = `teduh_coordinator`.

### REST API (M3-T7..T9, ditambah M5 & M6)
| Method | Path | Handler |
|---|---|---|
| GET | `/api/kelurahan` | GeoJSON + metrik untuk peta |
| GET | `/api/kelurahan/{kel_id}` | profil lengkap |
| POST | `/api/simulate` | skenario dari slider, tanpa LLM |
| POST | `/api/optimize` | portofolio dari form |
| POST | `/api/roof` | unggah foto → analisis + rekomendasi (M6) |
| GET | `/api/brief/{brief_id}` | brief Markdown/PDF (M5) |
| GET | `/api/model-card` | metrik dan batasan model |

Chat memakai endpoint ADK `/run_sse` (disediakan `get_fast_api_app`), bukan endpoint sendiri.

### Env var
```bash
GOOGLE_CLOUD_PROJECT=...
GOOGLE_CLOUD_LOCATION=asia-southeast2
GOOGLE_GENAI_USE_ENTERPRISE=True
TEDUH_MODEL=gemini-3.8-flash
TEDUH_DATA_URI=gs://<bucket>/teduh/v1/     # kosong = baca dari disk lokal
TEDUH_SINGLE_AGENT=0                       # 1 = fallback satu agen
NEXT_PUBLIC_TEDUH_API=http://localhost:8080
```

---

## Peta file yang akan dibuat

```
pyproject.toml                   M0-T1   dependensi + konfigurasi pytest/ruff
.env.example                     M0-T1   daftar env var, tanpa nilai rahasia
.dockerignore                    M0-T6

model/__init__.py                M0-T2
model/hvi.py                     M2-T1   percentile + formula HVI (dipakai pipeline & tools)
model/train.py                   M2-T2   LightGBM + spatial CV + monotonic + model card
model/explain.py                 M2-T3   SHAP per sel -> rata-rata per kelurahan
model/scenario.py                M3-T1   intervensi -> perubahan fitur -> prediksi ulang
model/costs.py                   M3-T2   luas -> IDR, membawa source

teduh_agent/__init__.py          M0-T4   from . import agent
teduh_agent/store.py             M0-T2   pemuat artefak tunggal (lru_cache)
teduh_agent/facts.py             M0-T3   tipe Fact + registry sesi
teduh_agent/agent.py             M0-T4   root_agent (hello tool) -> M4 (sub-agen penuh)
teduh_agent/prompts/__init__.py  M4-T1   loader prompt .md
teduh_agent/prompts/*.md         M4-T1   instruksi sistem Bahasa Indonesia
teduh_agent/sub_agents/*.py      M4-T2   4 sub-agen
teduh_agent/tools/areas.py       M3-T3   find_area, get_area_profile, rank, explain_drivers
teduh_agent/tools/scenario_tools.py M3-T4 simulate_intervention
teduh_agent/tools/optimize.py    M3-T5   optimize_portfolio (CP-SAT)
teduh_agent/tools/evidence.py    M3-T6   get_evidence
teduh_agent/tools/brief.py       M5-T1   validator + render + PDF
teduh_agent/tools/roof.py        M6-T1   vision + aturan rekomendasi

api/__init__.py                  M3-T7
api/schemas.py                   M3-T7   model Pydantic request/response
api/routes.py                    M3-T8   router /api/*
api/main.py                      M3-T9   get_fast_api_app + mount router + CORS

web/                             M7a/M7b Next.js (rincian di m7a- dan m7b-web-*.md)
infra/Dockerfile                 M0-T6   Python 3.12 + WeasyPrint system deps
infra/deploy_api.sh              M0-T7   gcloud run deploy
infra/firebase.json              M8-T3

tests/conftest.py                M0-T5   fixture store dari tests/fixtures/
tests/test_store.py              M0-T2
tests/test_facts.py              M0-T3
tests/test_hvi.py                M2-T1
tests/test_train.py              M2-T2
tests/test_explain.py            M2-T3
tests/test_scenario.py           M3-T1   WAJIB (CLAUDE.md): arah fisika
tests/test_costs.py              M3-T2
tests/test_areas.py              M3-T3
tests/test_scenario_tools.py     M3-T4
tests/test_optimize.py           M3-T5   WAJIB (CLAUDE.md): anggaran + keadilan
tests/test_evidence.py           M3-T6
tests/test_api.py                M3-T8
tests/test_provenance.py         M5-T1   WAJIB (CLAUDE.md): angka liar ditolak
tests/test_roof.py               M6-T1
tests/eval/run_golden.py         M8-T1   runner 20 golden questions
tests/eval/eval_roof.py          M8-T2   akurasi 30 foto berlabel
```

## Perubahan pada file yang sudah ada

| File | Perubahan | Task |
|---|---|---|
| `pipeline/aggregate_kelurahan.py` | Hapus `_percentile` lokal dan formula HVI inline; impor dari `model/hvi.py`. Output parquet harus identik sesudahnya. | M2-T1 |
| `.gitignore` | Tambah `data/model/`, `web/node_modules/`, `web/.next/`, `.env` | M0-T1 |
| `CLAUDE.md` | Isi bagian "Perintah" dengan perintah nyata setelah M0 | M0-T1 |
| `docs/DECISIONS.md` | Catat setiap penyimpangan baru dari CONCEPT yang muncul saat implementasi | sesuai kebutuhan |
