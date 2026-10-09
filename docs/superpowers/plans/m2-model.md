# M2 — Model Panas Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> Baca `docs/superpowers/plans/README.md` bagian **Global Constraints** dan **Interface Registry** sebelum mulai. Prasyarat: **M0 selesai** (`teduh_agent/store.py`, `tests/conftest.py`, `model/__init__.py` ada).

**Goal:** Melatih model LightGBM yang memprediksi LST dari fitur permukaan yang bisa diintervensi, memvalidasinya dengan spatial block CV, menjelaskannya dengan SHAP per kelurahan, dan menerbitkan `model_card.json` yang berisi metrik sebenarnya.

**Architecture:** `model/hvi.py` mengangkat formula HVI keluar dari `pipeline/aggregate_kelurahan.py` karena dibutuhkan dua tempat sekaligus — pipeline membakar HVI bobot default ke parquet, dan `rank_priority_areas(weights=...)` menghitung ulang saat runtime ketika perencana mengubah bobot dari UI. `model/train.py` melatih dengan monotonic constraints sehingga arah fisika terjamin oleh konstruksi, bukan oleh keberuntungan. `model/explain.py` meringkas SHAP per sel menjadi satu baris per kelurahan supaya panel "faktor pendorong" tidak perlu menghitung SHAP saat request.

**Tech Stack:** LightGBM, SHAP TreeExplainer, scikit-learn (GroupKFold, LinearRegression, metrik), pandas, numpy.

## Global Constraints

- **Jangan pakai lat/lon sebagai fitur** (CLAUDE.md aturan 5). Dengan koordinat, model menghafal geografi dan mesin skenario jadi tidak berguna.
- **Monotonic constraints wajib:** LST turun saat `ndvi`, `albedo`, `tree_frac`, `water_frac` naik; LST naik saat `built_frac`, `ndbi` naik (CONCEPT §7.3).
- **Spatial block CV wajib** (blok 1 km, `GroupKFold` 5 lipatan). **Jangan melaporkan metrik dari random split** (CLAUDE.md aturan 5).
- Target CONCEPT §7.3: **R² ≥ 0,75** pada spatial CV. Kalau hasil nyata di bawah itu, **laporkan angka sebenarnya di model card** dan jangan klaim 0,75 di proposal. Jangan mengubah skema validasi agar angkanya bagus.
- Sel `lst_quality == "low"` (28 sel) **dikecualikan dari latih** (DECISIONS 2026-10-09).
- Hasil model selalu dilabeli **indikatif**; model memprediksi suhu permukaan, bukan suhu udara.
- Identifier dan komentar: Inggris. `print()`: Bahasa Indonesia.
- Commit conventional, diakhiri `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`.

### Kenyataan data yang harus ditangani
- Di 75.608 sel `good`: `lst_c` punya **5 NaN**, `pop` punya **1.207 NaN**. Fitur lain nol NaN.
- `pop` NaN berarti raster WorldPop constrained tidak menempatkan penduduk di sel itu, jadi **isi 0,0**, bukan dibuang — sel tanpa penduduk tetap informasi termal yang sah.
- `grid_features.parquet` di-gitignore (7 MB). Kalau tidak ada, jalankan `uv run python -m pipeline.build_grid`.

---

## File Structure

| File | Tanggung jawab |
|---|---|
| `model/hvi.py` | Persentil dalam-kota + formula HVI + peringkat. Satu-satunya tempat aritmetika HVI hidup. |
| `model/train.py` | Siapkan data latih, blok spasial, CV, baseline linear, latih final, tulis `model.txt` + `model_card.json`. |
| `model/explain.py` | SHAP per sel → agregat per kelurahan ke `shap_by_kel.parquet`. |
| `pipeline/aggregate_kelurahan.py` | **Diubah**: impor dari `model/hvi.py`, hapus duplikat. Output harus identik. |

---

## Task M2-T1: Formula HVI bersama

**Files:**
- Create: `model/hvi.py`
- Modify: `pipeline/aggregate_kelurahan.py` (hapus `_percentile` di baris 42–44; ganti blok komponen+HVI+rank di baris 90–97 dengan panggilan ke `model.hvi`; tambah import)
- Test: `tests/test_hvi.py`

**Interfaces:**
- Consumes: fixture `fixture_store` dan `real_store` dari `tests/conftest.py` (M0-T3); `store.hvi_cfg` berbentuk `{"weights": {"wE": {"value": 0.4, ...}, ...}, "exposed_vulnerable": {...}}`.
- Produces:
  - `DEFAULT_WEIGHTS: dict[str, float] = {"wE": 0.4, "wS": 0.3, "wA": 0.3}`
  - `WEIGHT_KEYS = ("wE", "wS", "wA")`, `COMPONENT_COLUMNS = ("H", "E", "S", "A")`
  - `REQUIRED_COLUMNS = ("lst_c_mean", "pop_density", "vulnerable_share", "tree_frac_mean")`
  - `percentile(series: pd.Series) -> pd.Series`
  - `load_weights(hvi_cfg: dict) -> dict[str, float]`
  - `components(kel: pd.DataFrame) -> pd.DataFrame` — kolom `H, E, S, A`, index sama dengan input
  - `hvi(comp: pd.DataFrame, weights: dict[str, float] | None = None) -> pd.Series` — nama `"hvi"`
  - `rank(hvi_series: pd.Series) -> pd.Series` — nama `"hvi_rank"`, dtype `Int64`, 1 = paling rentan

- [x] **Step 1: Tulis tes yang gagal**

Buat `tests/test_hvi.py`:

```python
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
```

- [x] **Step 2: Jalankan tes untuk memastikan gagal**

Run: `uv run pytest tests/test_hvi.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'model.hvi'`

- [x] **Step 3: Tulis `model/hvi.py`**

```python
"""Heat Vulnerability Index: the IPCC hazard x exposure x vulnerability framing (CONCEPT §7.4).

Lifted out of pipeline/aggregate_kelurahan.py because the formula is needed in two places at
once. The pipeline bakes default-weight HVI into kelurahan_metrics.parquet, and
rank_priority_areas(weights=...) recomputes it at request time when a planner reweights the
policy choice from the UI. Two copies of this arithmetic would drift, and a drifting HVI
means the map and the ranking disagree about who is most vulnerable -- the one thing this
product cannot get wrong.

Every component is a within-city percentile, so every figure is relative to Jakarta and must
never be read as an absolute risk. The weights are a policy choice, not a measurement.
"""

import pandas as pd

DEFAULT_WEIGHTS: dict[str, float] = {"wE": 0.4, "wS": 0.3, "wA": 0.3}

WEIGHT_KEYS = ("wE", "wS", "wA")
COMPONENT_COLUMNS = ("H", "E", "S", "A")
REQUIRED_COLUMNS = ("lst_c_mean", "pop_density", "vulnerable_share", "tree_frac_mean")


def percentile(series: pd.Series) -> pd.Series:
    """Within-city percentile rank in [0, 1]. NaN stays NaN, never a middling 0.5."""
    return series.rank(pct=True, na_option="keep")


def load_weights(hvi_cfg: dict) -> dict[str, float]:
    """Read the default weights from config/hvi.yaml."""
    weights = {key: float(hvi_cfg["weights"][key]["value"]) for key in WEIGHT_KEYS}
    total = sum(weights.values())
    if abs(total - 1.0) > 1e-9:
        print(f"PERINGATAN: bobot HVI berjumlah {total:.3f}, bukan 1,0")
    return weights


def components(kel: pd.DataFrame) -> pd.DataFrame:
    """Hazard, exposure, sensitivity, and lack of adaptive capacity, each a percentile.

    A is inverted on purpose: it measures the ABSENCE of canopy, so the leafiest kelurahan
    scores lowest.
    """
    missing = [column for column in REQUIRED_COLUMNS if column not in kel.columns]
    if missing:
        raise KeyError(f"kolom wajib untuk HVI tidak ada: {missing}")
    return pd.DataFrame(
        {
            "H": percentile(kel["lst_c_mean"]),
            "E": percentile(kel["pop_density"]),
            "S": percentile(kel["vulnerable_share"]),
            "A": 1.0 - percentile(kel["tree_frac_mean"]),
        },
        index=kel.index,
    )


def hvi(comp: pd.DataFrame, weights: dict[str, float] | None = None) -> pd.Series:
    """HVI = H * (wE*E + wS*S + wA*A), bounded in [0, 1] because every term is.

    Weights arrive from the UI, so they are validated here rather than trusted.
    """
    active = DEFAULT_WEIGHTS if weights is None else weights
    missing = [key for key in WEIGHT_KEYS if key not in active]
    if missing:
        raise KeyError(f"bobot HVI tidak lengkap, kurang: {missing}")
    negative = [key for key in WEIGHT_KEYS if active[key] < 0]
    if negative:
        raise ValueError(f"bobot HVI tidak boleh negatif: {negative}")

    weighted = active["wE"] * comp["E"] + active["wS"] * comp["S"] + active["wA"] * comp["A"]
    return (comp["H"] * weighted).rename("hvi")


def rank(hvi_series: pd.Series) -> pd.Series:
    """1 = most vulnerable. method="min" so tied kelurahan share the better rank."""
    return hvi_series.rank(ascending=False, method="min").astype("Int64").rename("hvi_rank")
```

- [x] **Step 4: Jalankan tes untuk memastikan lulus**

Run: `uv run pytest tests/test_hvi.py -v`
Expected: PASS, 15 tes (3 terakhir di-skip kalau `grid_features.parquet` tidak ada).

- [x] **Step 5: Catat nilai pipeline sebelum refactor**

```bash
uv run python -c "
import pandas as pd
k = pd.read_parquet('data/processed/kelurahan_metrics.parquet').set_index('kel_id')
k[['H','E','S','A','hvi','hvi_rank']].to_csv('/tmp/teduh_hvi_before.csv')
print('tersimpan, 5 teratas:')
print(k.nsmallest(5,'hvi_rank')[['kel_name','hvi','hvi_rank']].to_string())
"
```

- [x] **Step 6: Refactor `pipeline/aggregate_kelurahan.py` agar memakai `model/hvi.py`**

Tambahkan import setelah `import yaml` (baris 23):

```python
from model.hvi import components, hvi, load_weights, percentile, rank
```

Hapus seluruh fungsi `_percentile` (baris 42–44 beserta docstring-nya).

Ganti pembacaan bobot di `main()` (baris 56–61) menjadi:

```python
    cfg = yaml.safe_load(HVI_CONFIG.read_text())
    weights = load_weights(cfg)
    hazard_min = cfg["exposed_vulnerable"]["hazard_percentile_min"]["value"]
```

Ganti pemanggilan persentil sel (baris 67) — hanya nama fungsinya yang berubah:

```python
    grid["cell_h"] = percentile(grid["lst_c"].where(grid["lst_quality"] == "good"))
```

Ganti blok komponen + HVI + rank (baris 90–97) menjadi:

```python
    comp = components(kel)
    kel[list(comp.columns)] = comp
    kel["hvi"] = hvi(comp, weights)
    kel["hvi_rank"] = rank(kel["hvi"])
```

- [x] **Step 7: Jalankan ulang pipeline dan buktikan nilainya tidak berubah**

Run: `uv run python -m pipeline.aggregate_kelurahan`
Expected: `check ok`, dan tabel 10 kelurahan prioritas masih dipimpin Kampung Rawa dengan HVI 0,931.

Run:
```bash
uv run python -c "
import pandas as pd
before = pd.read_csv('/tmp/teduh_hvi_before.csv').set_index('kel_id').sort_index()
after = pd.read_parquet('data/processed/kelurahan_metrics.parquet').set_index('kel_id').sort_index()
for col in ['H','E','S','A','hvi','hvi_rank']:
    delta = (after[col] - before[col]).abs().max()
    print(f'{col:9s} selisih maksimum {delta:.12f}')
    assert delta < 1e-12, f'{col} berubah setelah refactor'
print('refactor tidak mengubah nilai apa pun')
"
```
Expected: semua selisih 0, lalu `refactor tidak mengubah nilai apa pun`.

Perbandingan **nilai** yang menentukan, bukan hash file — Parquet bisa menghasilkan byte berbeda hanya karena metadata penulisan.

Run: `uv run pytest tests/test_hvi.py -v`
Expected: PASS semua, termasuk dua tes regresi terhadap kolom yang di-commit.

- [x] **Step 8: Commit**

```bash
git add model/hvi.py pipeline/aggregate_kelurahan.py tests/test_hvi.py
git commit -m "refactor: angkat formula HVI ke model/hvi.py agar bisa dihitung ulang saat runtime

Pipeline dan rank_priority_areas kini memakai satu implementasi yang sama, jadi bobot yang
diubah dari UI tidak bisa menghasilkan HVI yang berbeda dari peta.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task M2-T2: Latih LightGBM dengan spatial block CV

**Files:**
- Create: `model/train.py`
- Test: `tests/test_train.py`
- Output: `data/model/model.txt`, `data/model/model_card.json` (keduanya di-gitignore)

**Interfaces:**
- Consumes: `teduh_agent.store.good_cells` (M0-T3).
- Produces:
  - `FEATURES: list[str]` — 12 nama kolom, **tanpa** `lon`/`lat`
  - `TARGET = "lst_c"`
  - `MONOTONE: dict[str, int]` — 6 entri bertanda
  - `PARAMS: dict`, `NUM_ROUNDS = 600`, `BLOCK_M = 1000`, `N_FOLDS = 5`, `R2_TARGET = 0.75`, `R2_FLOOR = 0.60`
  - `MODEL_PATH`, `MODEL_CARD_PATH` — `pathlib.Path`
  - `monotone_constraints() -> list[int]`
  - `spatial_blocks(frame: pd.DataFrame, block_m: int = BLOCK_M) -> pd.Series`
  - `prepare(grid: pd.DataFrame) -> pd.DataFrame`
  - `cross_validate(frame: pd.DataFrame) -> list[dict]` — tiap dict: `fold, n_train, n_test, r2, rmse, mae`
  - `baseline_cross_validate(frame: pd.DataFrame) -> list[dict]`
  - `fit_final(frame: pd.DataFrame) -> lgb.Booster`
  - `predict(booster, frame: pd.DataFrame) -> np.ndarray`
  - `summarise(folds: list[dict]) -> dict` — `{"r2_mean", "r2_min", "rmse_mean", "mae_mean"}`
  - `main()`, `check(booster, frame, folds, baseline) -> None`

- [x] **Step 1: Tulis tes yang gagal**

Buat `tests/test_train.py`:

```python
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
```

- [x] **Step 2: Jalankan tes untuk memastikan gagal**

Run: `uv run pytest tests/test_train.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'model.train'`

- [x] **Step 3: Tulis `model/train.py`**

```python
"""LightGBM heat model with monotonic constraints and spatial block CV (CONCEPT §7.3).

Three decisions here are load-bearing and must not be relaxed to make a number look better.

1. No lat/lon features. Given coordinates the model memorises Jakarta's geography, and the
   scenario engine becomes useless: raising tree_frac would barely move the prediction
   because location already explains the heat. CLAUDE.md rule 5.

2. Monotonic constraints. LST must fall as ndvi, albedo, tree_frac and water_frac rise, and
   rise as built_frac and ndbi rise. This is the cheap version of physics-informed ML, and it
   is what makes tests/test_scenario.py's sign assertions true by construction rather than by
   luck. Without it a tree-planting scenario can come back as warming because of some
   correlational quirk, and the product would recommend the opposite of the right thing.

3. Spatial block CV, 1 km blocks via GroupKFold. LST is strongly autocorrelated at 100 m, so
   a random split leaks neighbouring cells between train and test and reports an R^2 that
   measures interpolation, not generalisation. Karurung et al. report 0.923 for Jakarta from a
   monthly panel; this is a one-season spatial cross-section, so a comparable number here
   would be a red flag, not a win. CONCEPT §7.3 targets 0.75 and says so explicitly.

Run: uv run python -m model.train
Output: data/model/model.txt, data/model/model_card.json
"""

import json
import math
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold

from teduh_agent.store import good_cells

ROOT = Path(__file__).resolve().parents[1]
GRID = ROOT / "data" / "processed" / "grid_features.parquet"
MODEL_DIR = ROOT / "data" / "model"
MODEL_PATH = MODEL_DIR / "model.txt"
MODEL_CARD_PATH = MODEL_DIR / "model_card.json"

# Interventionable surface features plus pop as an anthropogenic-heat proxy. NO lon/lat.
FEATURES: list[str] = [
    "albedo",
    "ndvi",
    "ndbi",
    "ndwi",
    "tree_frac",
    "built_frac",
    "water_frac",
    "roof_frac",
    "bldg_h_mean",
    "elev_m",
    "dist_coast_km",
    "pop",
]

TARGET = "lst_c"

# Simple physics, declared as constraints so the fitted surface cannot contradict it.
MONOTONE: dict[str, int] = {
    "albedo": -1,
    "ndvi": -1,
    "tree_frac": -1,
    "water_frac": -1,
    "built_frac": 1,
    "ndbi": 1,
}

PARAMS: dict = {
    "objective": "regression",
    "metric": "rmse",
    "learning_rate": 0.05,
    "num_leaves": 63,
    "min_data_in_leaf": 50,
    "feature_fraction": 0.9,
    "bagging_fraction": 0.8,
    "bagging_freq": 1,
    "lambda_l2": 1.0,
    "monotone_constraints_method": "advanced",
    "verbose": -1,
    "seed": 42,
    "deterministic": True,
}

NUM_ROUNDS = 600
BLOCK_M = 1000
N_FOLDS = 5

# CONCEPT §7.3 target. Reported honestly either way; the floor is what blocks a broken model.
R2_TARGET = 0.75
R2_FLOOR = 0.60

# Mean meridional metres per degree -- ample precision for kilometre-scale blocking.
M_PER_DEG_LAT = 111_320.0

DATA_PERIOD = "2023-2025 Jun-Sep (median musim kemarau)"
MODEL_VERSION = "lgbm@v1"


def monotone_constraints() -> list[int]:
    """Constraint signs positionally aligned with FEATURES, 0 where unconstrained."""
    return [MONOTONE.get(name, 0) for name in FEATURES]


def spatial_blocks(frame: pd.DataFrame, block_m: int = BLOCK_M) -> pd.Series:
    """Assign each cell to a 1 km square so GroupKFold holds out whole neighbourhoods."""
    mean_lat = float(frame["lat"].mean())
    metres_per_deg_lon = M_PER_DEG_LAT * math.cos(math.radians(mean_lat))

    east = (frame["lon"] - frame["lon"].min()) * metres_per_deg_lon
    north = (frame["lat"] - frame["lat"].min()) * M_PER_DEG_LAT

    block_x = (east // block_m).astype(int)
    block_y = (north // block_m).astype(int)
    return (block_x.astype(str) + "_" + block_y.astype(str)).rename("block")


def prepare(grid: pd.DataFrame) -> pd.DataFrame:
    """Training rows: good cells with a measured target and every feature present.

    pop NaN becomes 0.0 rather than being dropped. WorldPop Global2 is a constrained model
    that places residents only on built-up land, so a NaN means it placed nobody there --
    that is a real zero, and the cell's thermal signal is still valid.
    """
    frame = good_cells(grid).copy()
    frame[TARGET] = frame[TARGET].astype(float)
    frame = frame.dropna(subset=[TARGET])
    frame["pop"] = frame["pop"].fillna(0.0)

    before = len(frame)
    frame = frame.dropna(subset=FEATURES)
    dropped = before - len(frame)
    if dropped:
        print(f"peringatan  : {dropped} sel dibuang karena ada fitur kosong")
    return frame


def _train_booster(train: pd.DataFrame) -> lgb.Booster:
    constraints = monotone_constraints()
    dataset = lgb.Dataset(
        train[FEATURES],
        label=train[TARGET],
        feature_name=FEATURES,
        params={"monotone_constraints": constraints},
    )
    return lgb.train(
        {**PARAMS, "monotone_constraints": constraints},
        dataset,
        num_boost_round=NUM_ROUNDS,
    )


def _fold_metrics(fold: int, truth: np.ndarray, pred: np.ndarray, n_train: int) -> dict:
    return {
        "fold": fold,
        "n_train": int(n_train),
        "n_test": int(len(truth)),
        "r2": float(r2_score(truth, pred)),
        "rmse": float(math.sqrt(mean_squared_error(truth, pred))),
        "mae": float(mean_absolute_error(truth, pred)),
    }


def cross_validate(frame: pd.DataFrame) -> list[dict]:
    """Spatial block CV. Whole 1 km neighbourhoods are held out, never scattered cells."""
    blocks = spatial_blocks(frame)
    splitter = GroupKFold(n_splits=N_FOLDS)
    folds: list[dict] = []

    for index, (train_idx, test_idx) in enumerate(
        splitter.split(frame[FEATURES], frame[TARGET], groups=blocks)
    ):
        train, test = frame.iloc[train_idx], frame.iloc[test_idx]
        booster = _train_booster(train)
        pred = booster.predict(test[FEATURES])
        folds.append(_fold_metrics(index, test[TARGET].to_numpy(), pred, len(train)))
    return folds


def baseline_cross_validate(frame: pd.DataFrame) -> list[dict]:
    """Linear regression on the same folds (CONCEPT §7.3 asks for a baseline).

    If LightGBM does not beat this, the extra complexity is not earning its keep.
    """
    blocks = spatial_blocks(frame)
    splitter = GroupKFold(n_splits=N_FOLDS)
    folds: list[dict] = []

    for index, (train_idx, test_idx) in enumerate(
        splitter.split(frame[FEATURES], frame[TARGET], groups=blocks)
    ):
        train, test = frame.iloc[train_idx], frame.iloc[test_idx]
        model = LinearRegression().fit(train[FEATURES], train[TARGET])
        pred = model.predict(test[FEATURES])
        folds.append(_fold_metrics(index, test[TARGET].to_numpy(), pred, len(train)))
    return folds


def fit_final(frame: pd.DataFrame) -> lgb.Booster:
    """Fit on every training row. CV already told us how well this generalises."""
    return _train_booster(frame)


def predict(booster: lgb.Booster, frame: pd.DataFrame) -> np.ndarray:
    """Predict LST. Always slices FEATURES so a caller cannot leak an extra column in."""
    return np.asarray(booster.predict(frame[FEATURES]))


def summarise(folds: list[dict]) -> dict:
    """Mean plus the worst fold: a good average hiding one bad block is the thing to see."""
    return {
        "r2_mean": float(np.mean([f["r2"] for f in folds])),
        "r2_min": float(np.min([f["r2"] for f in folds])),
        "rmse_mean": float(np.mean([f["rmse"] for f in folds])),
        "mae_mean": float(np.mean([f["mae"] for f in folds])),
    }


def _model_card(frame: pd.DataFrame, folds: list[dict], baseline: list[dict]) -> dict:
    summary = summarise(folds)
    return {
        "version": MODEL_VERSION,
        "target": "Suhu permukaan tanah (LST), derajat Celsius",
        "target_caveat": (
            "Model memprediksi suhu PERMUKAAN, bukan suhu udara yang dirasakan warga. "
            "Semua hasil bersifat indikatif untuk penyaringan awal, bukan pengganti "
            "simulasi CFD atau ENVI-met."
        ),
        "data_period": DATA_PERIOD,
        "area": "DKI Jakarta daratan, tanpa Kepulauan Seribu",
        "n_train_cells": int(len(frame)),
        "n_kelurahan": int(frame["kel_id"].nunique()),
        "features": FEATURES,
        "monotone_constraints": MONOTONE,
        "excluded_features": {
            "lon_lat": "Koordinat sengaja tidak dipakai agar mesin skenario tetap responsif.",
            "no2": "Band nol di seluruh raster, dibuang (DECISIONS 2026-10-09).",
        },
        "validation": {
            "scheme": f"spatial block CV, blok {BLOCK_M} m, GroupKFold {N_FOLDS} lipatan",
            "why": (
                "LST sangat terautokorelasi pada 100 m, jadi random split membocorkan sel "
                "tetangga dan melaporkan R2 yang mengukur interpolasi, bukan generalisasi."
            ),
            "folds": folds,
            "summary": summary,
            "target_r2": R2_TARGET,
            "meets_target": bool(summary["r2_mean"] >= R2_TARGET),
            "baseline_linear": summarise(baseline),
        },
        "independent_checks": {
            "worldpop_vs_dukcapil": (
                "Total penduduk hasil klip ke 264 kelurahan 11.070.515 jiwa vs Dukcapil "
                "Semester I 2025 11.010.514 jiwa, selisih 0,54 persen."
            ),
            "bmkg_ghcn_tavg": (
                "Rata-rata suhu udara bulanan BMKG dan GHCN sepakat dalam 0,14 derajat C."
            ),
        },
        "limitations": [
            "Korelasional, bukan kausal. Monotonic constraints hanya menjaga arah.",
            "Satu musim (Jun-Sep), jadi tidak bisa dipakai untuk musim hujan.",
            "Tidak ada kovariat polusi setelah band NO2 dibuang.",
            "28 sel berkualitas rendah dikecualikan dari latih tetapi tetap tampil di peta.",
            "Harga cool roof dan green roof masih ASUMSI, bukan dari standar harga resmi.",
        ],
    }


def main() -> None:
    grid = pd.read_parquet(GRID)
    frame = prepare(grid)
    print(f"latih       : {len(frame):,} sel, {frame['kel_id'].nunique()} kelurahan")

    blocks = spatial_blocks(frame)
    print(f"blok spasial: {blocks.nunique()} blok {BLOCK_M} m untuk {N_FOLDS} lipatan")

    folds = cross_validate(frame)
    summary = summarise(folds)
    print("\nspatial block CV:")
    print(f"  {'lipatan':>8s} {'n_test':>8s} {'R2':>7s} {'RMSE':>7s} {'MAE':>7s}")
    for entry in folds:
        print(
            f"  {entry['fold']:8d} {entry['n_test']:8,d} "
            f"{entry['r2']:7.3f} {entry['rmse']:7.3f} {entry['mae']:7.3f}"
        )
    print(
        f"  rata-rata R2 {summary['r2_mean']:.3f} · terburuk {summary['r2_min']:.3f} · "
        f"RMSE {summary['rmse_mean']:.3f} C"
    )

    baseline = baseline_cross_validate(frame)
    print(f"baseline linear: R2 rata-rata {summarise(baseline)['r2_mean']:.3f}")

    booster = fit_final(frame)
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    booster.save_model(str(MODEL_PATH))
    MODEL_CARD_PATH.write_text(
        json.dumps(_model_card(frame, folds, baseline), indent=2, ensure_ascii=False)
    )
    print(f"\nwrote {MODEL_PATH.relative_to(ROOT)} dan {MODEL_CARD_PATH.relative_to(ROOT)}")

    check(booster, frame, folds, baseline)


def check(
    booster: lgb.Booster, frame: pd.DataFrame, folds: list[dict], baseline: list[dict]
) -> None:
    """Assert the guarantees the rest of the product leans on."""
    summary = summarise(folds)

    # Monotonicity is the behavioural contract behind every scenario result.
    probe = frame.head(200)
    base = predict(booster, probe)
    for name in ("ndvi", "tree_frac", "albedo", "water_frac"):
        greener = probe.copy()
        greener[name] = (greener[name] + 0.2).clip(upper=1.0)
        assert (predict(booster, greener) <= base + 1e-9).all(), (
            f"menaikkan {name} menaikkan prediksi LST -- monotonic constraint gagal"
        )
    for name in ("built_frac", "ndbi"):
        denser = probe.copy()
        denser[name] = (denser[name] + 0.2).clip(upper=1.0)
        assert (predict(booster, denser) >= base - 1e-9).all(), (
            f"menaikkan {name} menurunkan prediksi LST -- monotonic constraint gagal"
        )

    assert len(folds) == N_FOLDS, f"{len(folds)} lipatan, seharusnya {N_FOLDS}"
    assert summary["r2_mean"] > summarise(baseline)["r2_mean"], (
        "LightGBM tidak mengalahkan regresi linear; kompleksitasnya tidak terbayar"
    )
    assert summary["r2_mean"] >= R2_FLOOR, (
        f"R2 {summary['r2_mean']:.3f} di bawah batas bawah {R2_FLOOR}. "
        "Jangan ganti skema validasi untuk memperbaikinya -- periksa fitur dan datanya."
    )

    if summary["r2_mean"] < R2_TARGET:
        print(
            f"\nPERINGATAN: R2 {summary['r2_mean']:.3f} di bawah target CONCEPT "
            f"{R2_TARGET}. Angka sebenarnya sudah dicatat di model_card.json. "
            "JANGAN klaim 0,75 di proposal, video, atau brief."
        )
    print("check ok")


if __name__ == "__main__":
    main()
```

- [x] **Step 4: Jalankan tes untuk memastikan lulus**

Run: `uv run pytest tests/test_train.py -v`
Expected: PASS, 15 tes.

- [x] **Step 5: Latih model sebenarnya**

Run: `uv run python -m model.train`
Expected: tabel 5 lipatan tercetak, `check ok`, dan `data/model/model.txt` + `data/model/model_card.json` terbentuk. Perlu beberapa menit pada 75 ribu baris.

Catat `r2_mean` yang sebenarnya di sini: `0,755`. Angka ini yang masuk proposal dan halaman model card — **bukan** 0,78 seperti contoh di `design/README.md`.

Kalau `check` gagal pada assertion monotonic, jangan lepaskan constraint-nya; periksa bahwa `monotone_constraints` ikut terkirim ke `lgb.Dataset` **dan** ke `lgb.train`.

- [x] **Step 6: Commit**

```bash
git add model/train.py tests/test_train.py
git commit -m "feat: latih LightGBM dengan monotonic constraints dan spatial block CV

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task M2-T3: SHAP per kelurahan

**Files:**
- Create: `model/explain.py`
- Test: `tests/test_explain.py`
- Output: `data/model/shap_by_kel.parquet` (di-gitignore)

**Interfaces:**
- Consumes: `model.train.FEATURES`, `model.train.MODEL_PATH`, `model.train.predict`, `model.train.prepare` (M2-T2).
- Produces:
  - `SHAP_PATH = ROOT / "data" / "model" / "shap_by_kel.parquet"`
  - `SHAP_PREFIX = "shap_"`, `TOP_DRIVERS_DEFAULT = 5`, `MIN_CONTRIBUTION_C = 0.05`, `ADDITIVITY_TOLERANCE_C = 0.01`
  - `shap_values(booster, frame: pd.DataFrame) -> np.ndarray` — bentuk `(n_rows, len(FEATURES))`
  - `by_kelurahan(booster, frame: pd.DataFrame) -> pd.DataFrame` — kolom `kel_id`, `base_value`, `pred_lst_c`, `n_cells`, dan `shap_<feature>` untuk tiap `FEATURES`
  - `top_drivers(row: pd.Series, limit: int = TOP_DRIVERS_DEFAULT) -> list[dict]` — tiap dict `{"feature": str, "contribution_c": float, "direction": "memanaskan" | "mendinginkan"}`
  - `main()`, `check(table: pd.DataFrame) -> None`

`top_drivers` dipakai langsung oleh `explain_drivers` di M3-T3, jadi dia tinggal di sini, bukan di lapisan tool.

- [x] **Step 1: Tulis tes yang gagal**

Buat `tests/test_explain.py`:

```python
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
```

- [x] **Step 2: Jalankan tes untuk memastikan gagal**

Run: `uv run pytest tests/test_explain.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'model.explain'`

- [x] **Step 3: Tulis `model/explain.py`**

```python
"""SHAP attribution, pre-aggregated to one row per kelurahan.

Computing SHAP for 75_636 cells takes long enough that doing it per request would blow the
8 s latency target, so it is baked offline into shap_by_kel.parquet and the explain_drivers
tool just reads a row.

Averaging SHAP across a kelurahan's cells is legitimate because SHAP is additive in the
prediction: the mean contribution explains the mean prediction. That property is asserted in
check(), because design/README.md renders a divergent bar chart whose bars are required to
sum to the stated temperature difference -- a chart that does not add up is worse than no
chart.

Run: uv run python -m model.explain
Output: data/model/shap_by_kel.parquet
"""

from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
import shap

from model.train import FEATURES, MODEL_PATH, predict, prepare

ROOT = Path(__file__).resolve().parents[1]
GRID = ROOT / "data" / "processed" / "grid_features.parquet"
SHAP_PATH = ROOT / "data" / "model" / "shap_by_kel.parquet"

SHAP_PREFIX = "shap_"

# How many drivers the drawer shows (CONCEPT §8.2: "3-5 fitur SHAP teratas").
TOP_DRIVERS_DEFAULT = 5

# Contributions smaller than this are noise at the 0.1 C resolution the UI prints.
MIN_CONTRIBUTION_C = 0.05

ADDITIVITY_TOLERANCE_C = 0.01


def shap_values(booster: lgb.Booster, frame: pd.DataFrame) -> np.ndarray:
    """Per-cell SHAP values, shape (n_rows, len(FEATURES))."""
    explainer = shap.TreeExplainer(booster)
    return np.asarray(explainer.shap_values(frame[FEATURES]))


def _base_value(booster: lgb.Booster) -> float:
    explainer = shap.TreeExplainer(booster)
    return float(np.asarray(explainer.expected_value).reshape(-1)[0])


def by_kelurahan(booster: lgb.Booster, frame: pd.DataFrame) -> pd.DataFrame:
    """Mean SHAP contribution per feature per kelurahan, plus the mean prediction."""
    per_cell = pd.DataFrame(
        shap_values(booster, frame),
        columns=[f"{SHAP_PREFIX}{name}" for name in FEATURES],
        index=frame.index,
    )
    per_cell["kel_id"] = frame["kel_id"].to_numpy()
    per_cell["pred_lst_c"] = predict(booster, frame)

    grouped = per_cell.groupby("kel_id").mean()
    grouped["n_cells"] = per_cell.groupby("kel_id").size()
    grouped["base_value"] = _base_value(booster)
    return grouped.reset_index()


def top_drivers(row: pd.Series, limit: int = TOP_DRIVERS_DEFAULT) -> list[dict]:
    """The strongest contributions for one kelurahan, largest magnitude first.

    Direction labels are Indonesian because this feeds the drawer and the agent's prose
    directly; neither caller should have to interpret a sign.
    """
    contributions = [
        (name, float(row[f"{SHAP_PREFIX}{name}"]))
        for name in FEATURES
        if f"{SHAP_PREFIX}{name}" in row.index
    ]
    contributions.sort(key=lambda pair: abs(pair[1]), reverse=True)

    return [
        {
            "feature": name,
            "contribution_c": value,
            "direction": "memanaskan" if value > 0 else "mendinginkan",
        }
        for name, value in contributions[:limit]
        if abs(value) >= MIN_CONTRIBUTION_C
    ]


def main() -> None:
    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"{MODEL_PATH} tidak ada. Jalankan dulu: uv run python -m model.train"
        )
    booster = lgb.Booster(model_file=str(MODEL_PATH))
    frame = prepare(pd.read_parquet(GRID))
    print(f"SHAP        : {len(frame):,} sel, {frame['kel_id'].nunique()} kelurahan")

    table = by_kelurahan(booster, frame)
    SHAP_PATH.parent.mkdir(parents=True, exist_ok=True)
    table.to_parquet(SHAP_PATH, index=False)
    print(f"wrote {SHAP_PATH.relative_to(ROOT)} ({len(table)} baris, {len(table.columns)} kolom)")

    hottest = table.nlargest(1, "pred_lst_c").iloc[0]
    print(
        f"\nfaktor pendorong teratas di {hottest['kel_id']} "
        f"(prediksi {hottest['pred_lst_c']:.2f} C):"
    )
    for driver in top_drivers(hottest):
        print(
            f"  {driver['feature']:16s} {driver['contribution_c']:+6.2f} C  "
            f"{driver['direction']}"
        )

    check(table)


def check(table: pd.DataFrame) -> None:
    """Additivity is a product requirement: the drawer's bars must sum to the total."""
    assert table["kel_id"].is_unique, "ada kel_id ganda di tabel SHAP"

    contributions = table[[f"{SHAP_PREFIX}{name}" for name in FEATURES]].sum(axis=1)
    residual = (table["base_value"] + contributions - table["pred_lst_c"]).abs()
    assert residual.max() < ADDITIVITY_TOLERANCE_C, (
        f"kontribusi SHAP tidak menjumlah ke prediksi, selisih maksimum {residual.max():.4f} C"
    )

    print(f"  additivitas: selisih maksimum {residual.max():.5f} C")
    print(f"  base value : {table['base_value'].iloc[0]:.3f} C")
    print("check ok")


if __name__ == "__main__":
    main()
```

- [x] **Step 4: Jalankan tes untuk memastikan lulus**

Run: `uv run pytest tests/test_explain.py -v`
Expected: PASS, 7 tes.

- [x] **Step 5: Hasilkan SHAP sebenarnya**

Run: `uv run python -m model.explain`
Expected: `data/model/shap_by_kel.parquet` terbentuk dengan 264 baris, `check ok`, selisih additivitas di bawah 0,01 °C.

- [x] **Step 6: Verifikasi store sekarang memuat artefak model**

Run:
```bash
uv run python -c "
from teduh_agent.store import load
s = load()
print('booster  :', type(s.booster).__name__)
print('shap rows:', len(s.shap_by_kel))
print('R2 CV    :', s.model_card['validation']['summary']['r2_mean'])
"
```
Expected: `Booster`, `264`, dan nilai R² yang sama dengan hasil latih.

- [x] **Step 7: Jalankan seluruh suite**

Run: `uv run pytest -q`
Expected: hijau semua.

- [x] **Step 8: Commit**

```bash
git add model/explain.py tests/test_explain.py
git commit -m "feat: hasilkan SHAP per kelurahan dengan jaminan additivitas

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Definisi M2 selesai

- [x] `model/hvi.py` mereproduksi kolom `hvi` dan `hvi_rank` yang sudah di-commit, dan `pipeline/aggregate_kelurahan.py` tidak lagi punya duplikat formula.
- [x] `uv run python -m model.train` menghasilkan `model.txt` + `model_card.json`, `check ok`, dan LightGBM mengalahkan baseline linear.
- [x] Monotonic constraints terbukti terpasang: menaikkan `ndvi`/`tree_frac`/`albedo`/`water_frac` tidak pernah menaikkan prediksi.
- [x] R² spatial CV sebenarnya tercatat di `model_card.json`. Kalau < 0,75, peringatan tercetak dan **angka itu** yang dipakai di proposal.
- [x] `uv run python -m model.explain` menghasilkan `shap_by_kel.parquet` 264 baris dengan selisih additivitas < 0,01 °C.
- [x] `uv run pytest -q` hijau.

**Selanjutnya:** [`m3-scenario-engine.md`](m3-scenario-engine.md) — mesin skenario dan biaya, lalu [`m3-tools.md`](m3-tools.md) dan [`m3-api.md`](m3-api.md).
