# M3a — Mesin Skenario dan Biaya Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> Baca `docs/superpowers/plans/README.md` bagian **Global Constraints** dan **Interface Registry** sebelum mulai. Prasyarat: **M0 dan M2 selesai** (`teduh_agent/store.py` ada, `model/train.py` sudah menghasilkan `data/model/model.txt`).

**Goal:** Menerjemahkan intervensi (pohon, cool roof, green roof) menjadi perubahan fitur yang jujur, memprediksi ulang LST dengan model, dan menghitung biayanya dari harga bersumber — tanpa satu pun konstanta karangan.

**Architecture:** `model/scenario.py` memegang satu fungsi kunci, `treated_fractions()`, yang menghitung berapa bagian luas tiap sel benar-benar tersentuh tiap intervensi setelah dibatasi kenyataan fisik. `apply_interventions()` dan `intervened_area_m2()` sama-sama membaca dari fungsi itu, sehingga luas yang dibiayai selalu persis luas yang disimulasikan. `model/costs.py` sengaja tidak mengimpor `scenario.py` agar tidak ada siklus impor; keselarasan nama intervensi dijaga oleh sebuah tes.

**Tech Stack:** pandas, numpy, LightGBM (lewat `model.train.predict`), konfigurasi YAML lewat store.

## Global Constraints

- **Jangan mengarang konstanta** (CLAUDE.md aturan 4). Semua angka lewat `store.config_entry()`, yang menolak entri tanpa `source`.
- **Arah fisika dijamin di hulu** oleh monotonic constraints `model/train.py`, bukan oleh modul ini. Tugas modul ini adalah membuat delta fitur jujur.
- `tests/test_scenario.py` adalah tes **wajib** menurut CLAUDE.md: menambah pohon atau albedo tidak pernah menaikkan LST, dan ekstrapolasi diberi flag.
- Jangan mutasi input — `apply_interventions` mengembalikan salinan baru.
- Identifier dan komentar: Inggris. Teks pengguna: Bahasa Indonesia.
- Commit conventional, diakhiri `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`.

### Konstanta yang tersedia (jangan tambah selain yang disebut di Task M3-T1 Step 1)

`config/scenario.yaml`: `tree_planting.ndvi_tree` = 0,6450 (`data:grid_features@v1`) · `tree_planting.canopy_frac_threshold` = 0,8 · `cool_roof.albedo_cool` = 0,65 (ASUMSI) · `cool_roof.albedo_roof_base` = 0,15 (ASUMSI) · `green_roof.flat_roof_share` = 0,2 (ASUMSI) · `green_roof.albedo_green` = 0,2 (ASUMSI) · `extrapolation.feature_percentile_max` = 99 · `extrapolation.min_cooling_for_benefit_c` = −0,5

`config/costs.yaml`: `tree_planting.tree_unit_idr` = 2.702.703 (Kepgub 811/2025 item 696.19) · `tree_planting.planting_unit_idr` = 1.950.000 (Kepgub item 660.91, proxy relokasi) · `tree_planting.canopy_m2_per_tree` = 12,0 (ASUMSI) · `cool_roof.cost_idr_per_m2` = 95.000 (ASUMSI) · `green_roof.cost_idr_per_m2` = 600.000 (ASUMSI) · `optimizer.equity_share_min` = 0,6

---

## File Structure

| File | Tanggung jawab |
|---|---|
| `model/scenario.py` | Intervensi → fraksi luas tersentuh → delta fitur → prediksi ulang → `ScenarioResult`. |
| `model/costs.py` | Luas (m²) → rupiah, membawa daftar `source` untuk tiap angka yang dipakai. |
| `config/scenario.yaml` | **Diubah**: tambah satu entri `green_roof.ndvi_green`. |

---

## Task M3-T1: Mesin skenario

**Files:**
- Create: `model/scenario.py`
- Modify: `config/scenario.yaml` (tambah `green_roof.ndvi_green`)
- Modify: `docs/DECISIONS.md` (catat asumsi baru)
- Test: `tests/test_scenario.py`

**Interfaces:**
- Consumes: `teduh_agent.store.config_entry` (M0-T3); `model.train.FEATURES`, `model.train.predict` (M2-T2); `model.costs.intervention_cost`, `model.costs.CELL_AREA_M2` (M3-T2 — kerjakan T2 lebih dulu, atau kerjakan T1 dan T2 bersamaan).
- Produces:
  - `TREE = "tree_planting"`, `COOL_ROOF = "cool_roof"`, `GREEN_ROOF = "green_roof"`
  - `INTERVENTION_TYPES: tuple[str, str, str]`
  - `PARAM_NAME: dict[str, str]` — `{TREE: "canopy_increase_pp", COOL_ROOF: "adoption_rate", GREEN_ROOF: "adoption_rate"}`
  - `LEVELS: dict[str, dict[str, float]]`
  - `Intervention` — frozen dataclass `(type: str, params: dict)`
  - `ScenarioResult` — frozen dataclass, field: `kel_id, delta_lst_c, delta_lst_pop_weighted_c, vulnerable_benefiting, area_m2, area_by_type, cost_idr, cost_sources, extrapolation, extrapolated_features, n_cells`
  - `from_level(itype: str, level: str) -> Intervention`
  - `plantable_headroom(cells: pd.DataFrame) -> pd.Series`
  - `treated_fractions(cells, interventions, scenario_cfg) -> dict[str, pd.Series]`
  - `apply_interventions(cells, interventions, scenario_cfg) -> pd.DataFrame`
  - `intervened_area_m2(cells, interventions, scenario_cfg) -> dict[str, float]`
  - `training_quantiles(frame: pd.DataFrame, percentile: float | None = None) -> pd.Series`
  - `simulate(cells, interventions, booster, scenario_cfg, costs_cfg, train_q99) -> ScenarioResult`

- [ ] **Step 1: Tambah konstanta NDVI green roof ke `config/scenario.yaml`**

CONCEPT §7.5 menyebut green roof menaikkan NDVI pada porsi atap datar, tetapi tidak memberi nilai targetnya. Memakai `ndvi_tree` (0,6450, kanopi pohon penuh) akan melebih-lebihkan: green roof ekstensif ditanami sedum dan rumput, bukan pohon. Karena tidak ada sumber Indonesia yang bisa diakses, ini menjadi ASUMSI berlabel — bukan angka yang diam-diam dipinjam dari konstanta lain.

Tambahkan di dalam blok `green_roof` yang sudah ada di `config/scenario.yaml`:

```yaml
  ndvi_green:
    value: 0.35
    unit: "ndvi"
    source: "ASUMSI"
    note: >
      NDVI permukaan green roof ekstensif (sedum, rumput, semak rendah) saat tumbuh penuh.
      Sengaja JAUH di bawah ndvi_tree 0,6450, yang merupakan kanopi pohon penuh: memakai
      angka pohon untuk atap bersedum akan melebihkan pendinginan green roof hampir dua
      kali. Tidak ada sumber Indonesia yang bisa diakses untuk NDVI atap hijau tropis, jadi
      ini tetap ASUMSI sampai ada pengukuran. 0,35 duduk di tengah rentang rumput sehat
      (0,3-0,5).
```

- [ ] **Step 2: Catat asumsi baru di `docs/DECISIONS.md`**

Tambahkan sebelum baris penutup (`Rincian semua sumber: docs/DATA_SOURCES.md.`):

```markdown
## 2026-10-09 — `green_roof.ndvi_green` = 0,35 adalah ASUMSI baru, bukan pinjaman dari `ndvi_tree`

- **Konsep (§7.5):** "ndvi naik pada porsi atap tersebut" — nilai targetnya tidak disebut.
- **Keputusan:** entri baru `green_roof.ndvi_green` = 0,35 dengan `source: "ASUMSI"`.
- **Alasan:** satu-satunya konstanta NDVI yang sudah ada adalah `ndvi_tree` = 0,6450, median sel berkanopi pohon > 80%. Memakainya untuk green roof ekstensif (sedum/rumput) akan melebihkan pendinginan green roof hampir dua kali lipat. Lebih jujur menambah asumsi berlabel daripada diam-diam memakai angka yang salah konteks.
- **Risiko:** belum terukur. Kalau nanti ada pengukuran NDVI atap hijau tropis, ganti nilainya beserta `source`-nya.
```

- [ ] **Step 3: Tulis tes yang gagal**

Buat `tests/test_scenario.py`:

```python
"""WAJIB menurut CLAUDE.md: adding trees or albedo must never raise LST, and extrapolation
must be flagged.

The sign tests are the product's core safety property. If they fail, TEDUH is recommending
the opposite of the right thing to a city government, which is worse than recommending
nothing at all."""

import numpy as np
import pandas as pd
import pytest

from model.scenario import (
    COOL_ROOF,
    GREEN_ROOF,
    INTERVENTION_TYPES,
    LEVELS,
    TREE,
    Intervention,
    apply_interventions,
    from_level,
    intervened_area_m2,
    plantable_headroom,
    simulate,
    training_quantiles,
    treated_fractions,
)
from model.train import FEATURES, fit_final, prepare


@pytest.fixture(scope="module")
def trained(fixture_store):
    frame = prepare(fixture_store.grid)
    return fit_final(frame), frame


@pytest.fixture
def cells(fixture_store):
    """One kelurahan's cells: Kampung Rawa, the bare dense one."""
    grid = fixture_store.grid
    return grid[grid["kel_id"] == "ID3173040002"].copy()


@pytest.fixture
def cfg(fixture_store):
    return fixture_store.scenario_cfg


@pytest.fixture
def costs(fixture_store):
    return fixture_store.costs_cfg


def _one_cell(**overrides) -> pd.DataFrame:
    """A single synthetic cell, so a test can vary exactly one physical property."""
    row = {
        "built_frac": 0.5,
        "water_frac": 0.0,
        "tree_frac": 0.0,
        "roof_frac": 0.4,
        "ndvi": 0.2,
        "albedo": 0.13,
    }
    row.update(overrides)
    return pd.DataFrame([row])


# --- intervention construction -------------------------------------------------------

@pytest.mark.unit
def test_every_intervention_type_has_three_levels():
    for itype in INTERVENTION_TYPES:
        assert set(LEVELS[itype]) == {"low", "medium", "high"}


@pytest.mark.unit
def test_levels_increase_monotonically():
    for itype in INTERVENTION_TYPES:
        low, medium, high = (LEVELS[itype][key] for key in ("low", "medium", "high"))
        assert low < medium < high


@pytest.mark.unit
def test_from_level_builds_the_right_parameter_name():
    assert from_level(TREE, "medium").params == {"canopy_increase_pp": LEVELS[TREE]["medium"]}
    assert from_level(COOL_ROOF, "high").params == {"adoption_rate": LEVELS[COOL_ROOF]["high"]}


@pytest.mark.unit
def test_from_level_rejects_an_unknown_type():
    with pytest.raises(ValueError, match="intervensi"):
        from_level("cool_pavement", "low")


@pytest.mark.unit
def test_from_level_rejects_an_unknown_level():
    with pytest.raises(ValueError, match="level"):
        from_level(TREE, "ekstrem")


# --- physical caps -------------------------------------------------------------------

@pytest.mark.unit
def test_plantable_headroom_is_zero_on_a_fully_built_cell():
    assert plantable_headroom(_one_cell(built_frac=1.0)).iloc[0] == 0.0


@pytest.mark.unit
def test_plantable_headroom_is_zero_on_open_water():
    assert plantable_headroom(_one_cell(built_frac=0.0, water_frac=1.0)).iloc[0] == 0.0


@pytest.mark.unit
def test_plantable_headroom_excludes_canopy_that_already_exists():
    cell = _one_cell(built_frac=0.3, water_frac=0.1, tree_frac=0.4)
    assert plantable_headroom(cell).iloc[0] == pytest.approx(0.2)


@pytest.mark.integration
def test_canopy_gain_is_capped_by_available_land(cfg):
    # Asking for 20 pp of new canopy on a cell with 5 pp of bare ground must plant 5 pp.
    cell = _one_cell(built_frac=0.95, roof_frac=0.9)
    fractions = treated_fractions(cell, [Intervention(TREE, {"canopy_increase_pp": 20.0})], cfg)
    assert fractions[TREE].iloc[0] == pytest.approx(0.05)


@pytest.mark.integration
def test_cool_roof_only_treats_roof_that_exists(cfg):
    fractions = treated_fractions(
        _one_cell(), [Intervention(COOL_ROOF, {"adoption_rate": 0.5})], cfg
    )
    assert fractions[COOL_ROOF].iloc[0] == pytest.approx(0.2)


@pytest.mark.integration
def test_green_roof_only_treats_the_flat_share_of_the_roof(cfg):
    # flat_roof_share is 0.2, so half adoption on a 0.4 roof gives 0.4 * 0.2 * 0.5 = 0.04.
    fractions = treated_fractions(
        _one_cell(), [Intervention(GREEN_ROOF, {"adoption_rate": 0.5})], cfg
    )
    assert fractions[GREEN_ROOF].iloc[0] == pytest.approx(0.04)


@pytest.mark.integration
def test_cool_roof_and_green_roof_do_not_double_count_the_same_roof(cfg):
    # Both at full adoption must not treat more roof than the cell actually has.
    fractions = treated_fractions(
        _one_cell(roof_frac=0.5, built_frac=0.6),
        [
            Intervention(COOL_ROOF, {"adoption_rate": 1.0}),
            Intervention(GREEN_ROOF, {"adoption_rate": 1.0}),
        ],
        cfg,
    )
    treated_roof = fractions[COOL_ROOF].iloc[0] + fractions[GREEN_ROOF].iloc[0]
    assert treated_roof <= 0.5 + 1e-9


@pytest.mark.integration
def test_duplicate_intervention_types_are_rejected(cfg):
    with pytest.raises(ValueError, match="ganda"):
        treated_fractions(
            _one_cell(),
            [
                Intervention(TREE, {"canopy_increase_pp": 1.0}),
                Intervention(TREE, {"canopy_increase_pp": 2.0}),
            ],
            cfg,
        )


# --- feature deltas ------------------------------------------------------------------

@pytest.mark.integration
def test_apply_interventions_does_not_mutate_its_input(cells, cfg):
    before = cells["tree_frac"].copy()
    apply_interventions(cells, [from_level(TREE, "high")], cfg)
    pd.testing.assert_series_equal(cells["tree_frac"], before)


@pytest.mark.integration
def test_planting_raises_canopy_and_greenness(cells, cfg):
    after = apply_interventions(cells, [from_level(TREE, "high")], cfg)
    assert (after["tree_frac"] >= cells["tree_frac"]).all()
    assert (after["ndvi"] >= cells["ndvi"] - 1e-12).all()


@pytest.mark.integration
def test_planting_never_pushes_ndvi_above_the_calibrated_tree_value(cells, cfg):
    ndvi_tree = cfg["tree_planting"]["ndvi_tree"]["value"]
    after = apply_interventions(cells, [from_level(TREE, "high")], cfg)
    assert after["ndvi"].max() <= max(ndvi_tree, cells["ndvi"].max()) + 1e-9


@pytest.mark.integration
def test_cool_roof_raises_albedo(cells, cfg):
    after = apply_interventions(cells, [from_level(COOL_ROOF, "high")], cfg)
    assert (after["albedo"] >= cells["albedo"]).all()


@pytest.mark.integration
def test_feature_fractions_stay_physically_bounded(cells, cfg):
    after = apply_interventions(
        cells,
        [from_level(TREE, "high"), from_level(COOL_ROOF, "high"), from_level(GREEN_ROOF, "high")],
        cfg,
    )
    for column in ("tree_frac", "built_frac", "water_frac", "roof_frac", "albedo", "ndvi"):
        assert after[column].between(0.0, 1.0).all(), f"{column} keluar dari [0,1]"


# --- the mandatory sign guarantees ---------------------------------------------------

@pytest.mark.integration
def test_planting_trees_never_warms_a_kelurahan(trained, cells, cfg, costs):
    # CLAUDE.md names this test explicitly.
    booster, frame = trained
    q99 = training_quantiles(frame)
    for level in ("low", "medium", "high"):
        result = simulate(cells, [from_level(TREE, level)], booster, cfg, costs, q99)
        assert result.delta_lst_c <= 1e-9, f"pohon level {level} menaikkan LST"


@pytest.mark.integration
def test_cool_roof_never_warms_a_kelurahan(trained, cells, cfg, costs):
    booster, frame = trained
    q99 = training_quantiles(frame)
    for level in ("low", "medium", "high"):
        result = simulate(cells, [from_level(COOL_ROOF, level)], booster, cfg, costs, q99)
        assert result.delta_lst_c <= 1e-9, f"cool roof level {level} menaikkan LST"


@pytest.mark.integration
def test_doing_nothing_changes_nothing(trained, cells, cfg, costs):
    booster, frame = trained
    result = simulate(cells, [], booster, cfg, costs, training_quantiles(frame))
    assert result.delta_lst_c == pytest.approx(0.0, abs=1e-12)
    assert result.cost_idr == 0.0


@pytest.mark.integration
def test_a_stronger_intervention_cools_at_least_as_much(trained, cells, cfg, costs):
    booster, frame = trained
    q99 = training_quantiles(frame)
    low = simulate(cells, [from_level(TREE, "low")], booster, cfg, costs, q99)
    high = simulate(cells, [from_level(TREE, "high")], booster, cfg, costs, q99)
    assert high.delta_lst_c <= low.delta_lst_c + 1e-9


# --- extrapolation flag ---------------------------------------------------------------

@pytest.mark.integration
def test_an_absurd_scenario_is_flagged_as_extrapolation(trained, cells, cfg, costs):
    # CLAUDE.md: "ekstrapolasi diberi flag". Pushing albedo far past anything in the
    # training data must be reported, not silently predicted.
    booster, frame = trained
    loud = cells.copy()
    loud["roof_frac"] = 1.0

    result = simulate(
        loud,
        [Intervention(COOL_ROOF, {"adoption_rate": 1.0})],
        booster,
        cfg,
        costs,
        training_quantiles(frame),
    )

    assert result.extrapolation is True
    assert result.extrapolated_features


@pytest.mark.integration
def test_a_modest_scenario_is_not_flagged(trained, cells, cfg, costs):
    booster, frame = trained
    result = simulate(
        cells, [from_level(TREE, "low")], booster, cfg, costs, training_quantiles(frame)
    )
    assert result.extrapolation is False


@pytest.mark.integration
def test_training_quantiles_cover_every_model_feature(trained):
    _, frame = trained
    assert set(training_quantiles(frame).index) == set(FEATURES)


# --- result bookkeeping ---------------------------------------------------------------

@pytest.mark.integration
def test_result_reports_the_kelurahan_and_cell_count(trained, cells, cfg, costs):
    booster, frame = trained
    result = simulate(
        cells, [from_level(TREE, "low")], booster, cfg, costs, training_quantiles(frame)
    )
    assert result.kel_id == "ID3173040002"
    assert result.n_cells == len(cells)


@pytest.mark.integration
def test_simulate_rejects_a_mixed_kelurahan_frame(trained, fixture_store, cfg, costs):
    booster, frame = trained
    with pytest.raises(ValueError, match="satu kelurahan"):
        simulate(
            fixture_store.grid, [from_level(TREE, "low")], booster, cfg, costs,
            training_quantiles(frame),
        )


@pytest.mark.integration
def test_area_billed_equals_area_simulated(trained, cells, cfg, costs):
    # The whole point of sharing treated_fractions(): a planner must never be charged for
    # more square metres than the model was told about.
    booster, frame = trained
    interventions = [from_level(TREE, "medium"), from_level(COOL_ROOF, "medium")]
    result = simulate(cells, interventions, booster, cfg, costs, training_quantiles(frame))
    areas = intervened_area_m2(cells, interventions, cfg)
    assert result.area_m2 == pytest.approx(sum(areas.values()))
    assert set(result.area_by_type) == set(areas)


@pytest.mark.integration
def test_cost_sources_are_carried_so_facts_can_cite_them(trained, cells, cfg, costs):
    booster, frame = trained
    result = simulate(
        cells, [from_level(TREE, "low")], booster, cfg, costs, training_quantiles(frame)
    )
    assert result.cost_idr > 0
    assert result.cost_sources, "biaya tanpa source tidak boleh lolos (CLAUDE.md aturan 4)"


@pytest.mark.integration
def test_vulnerable_benefiting_never_exceeds_the_vulnerable_population(
    trained, cells, cfg, costs
):
    booster, frame = trained
    result = simulate(
        cells, [from_level(TREE, "high")], booster, cfg, costs, training_quantiles(frame)
    )
    total_vulnerable = (cells["pop_u5"].fillna(0) + cells["pop_65p"].fillna(0)).sum()
    assert result.vulnerable_benefiting <= total_vulnerable + 1e-6


@pytest.mark.integration
def test_population_weighted_delta_is_finite_even_with_unpopulated_cells(
    trained, cells, cfg, costs
):
    # 1_207 good cells have NaN pop. A naive weighted mean returns NaN and the UI would
    # print "NaN °C" to a planner.
    booster, frame = trained
    empty = cells.copy()
    empty["pop"] = np.nan
    result = simulate(
        empty, [from_level(TREE, "low")], booster, cfg, costs, training_quantiles(frame)
    )
    assert np.isfinite(result.delta_lst_pop_weighted_c)
```

- [ ] **Step 4: Jalankan tes untuk memastikan gagal**

Run: `uv run pytest tests/test_scenario.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'model.scenario'`

- [ ] **Step 5: Tulis `model/scenario.py`**

```python
"""Translate an intervention into feature changes, then ask the model for a new LST.

CONCEPT §7.5. The engine never invents a constant: every number comes through
store.config_entry(), which refuses an entry that has no source.

The physics DIRECTION is guaranteed upstream by the monotonic constraints in
model/train.py, not by anything here. This module's job is to keep the feature deltas
honest, which means respecting three caps that are easy to forget:

  - canopy cannot be planted on buildings or open water, nor on ground that already carries
    canopy, so the gain is capped by the cell's remaining plantable headroom;
  - cool roof only repaints roof area that exists, so the treated fraction scales with
    roof_frac;
  - green roof only applies to the flat share of that roof area, and must not be charged for
    roof the cool-roof intervention already took.

Skipping those caps is how a scenario tool starts promising 10 pp of new canopy in a cell
that is 100 % built, and then billing a city for it.

treated_fractions() is the single source of truth for "how much of this cell is touched".
apply_interventions() and intervened_area_m2() both read from it, which is what guarantees
the area billed equals the area simulated.
"""

from dataclasses import dataclass

import lightgbm as lgb
import numpy as np
import pandas as pd

from model.costs import CELL_AREA_M2, intervention_cost
from model.train import FEATURES, predict
from teduh_agent.store import config_entry

TREE = "tree_planting"
COOL_ROOF = "cool_roof"
GREEN_ROOF = "green_roof"

INTERVENTION_TYPES: tuple[str, str, str] = (TREE, COOL_ROOF, GREEN_ROOF)

PARAM_NAME: dict[str, str] = {
    TREE: "canopy_increase_pp",
    COOL_ROOF: "adoption_rate",
    GREEN_ROOF: "adoption_rate",
}

# Levels the optimiser enumerates and the UI sliders snap to (CONCEPT §7.6).
# tree_planting is in percentage points of cell area; the roof measures are adoption rates.
LEVELS: dict[str, dict[str, float]] = {
    TREE: {"low": 2.0, "medium": 5.0, "high": 10.0},
    COOL_ROOF: {"low": 0.25, "medium": 0.50, "high": 0.75},
    GREEN_ROOF: {"low": 0.10, "medium": 0.20, "high": 0.35},
}

PERCENTAGE_POINTS = 100.0

# Features clipped back into their physical range after the deltas land.
BOUNDED_FEATURES = ("tree_frac", "built_frac", "water_frac", "roof_frac", "albedo", "ndvi")


@dataclass(frozen=True)
class Intervention:
    """One intervention at one intensity. The params key is given by PARAM_NAME."""

    type: str
    params: dict


@dataclass(frozen=True)
class ScenarioResult:
    """What one kelurahan gets from one set of interventions.

    delta_lst_c is negative when the scenario cools, which is the desirable direction.
    """

    kel_id: str
    delta_lst_c: float
    delta_lst_pop_weighted_c: float
    vulnerable_benefiting: float
    area_m2: float
    area_by_type: dict[str, float]
    cost_idr: float
    cost_sources: tuple[str, ...]
    extrapolation: bool
    extrapolated_features: tuple[str, ...]
    n_cells: int


def from_level(itype: str, level: str) -> Intervention:
    """Build an Intervention from a named intensity."""
    if itype not in INTERVENTION_TYPES:
        raise ValueError(f"jenis intervensi tidak dikenal: {itype!r}")
    if level not in LEVELS[itype]:
        raise ValueError(f"level tidak dikenal untuk {itype}: {level!r}")
    return Intervention(itype, {PARAM_NAME[itype]: LEVELS[itype][level]})


def plantable_headroom(cells: pd.DataFrame) -> pd.Series:
    """Fraction of each cell that could still take new canopy.

    Buildings and water are unplantable, and ground already under canopy cannot be planted
    twice. Clipped at zero because the three fractions are measured independently and can
    sum slightly past 1.
    """
    headroom = 1.0 - cells["built_frac"] - cells["water_frac"] - cells["tree_frac"]
    return headroom.clip(lower=0.0, upper=1.0)


def _by_type(interventions: list[Intervention]) -> dict[str, Intervention]:
    chosen: dict[str, Intervention] = {}
    for intervention in interventions:
        if intervention.type not in INTERVENTION_TYPES:
            raise ValueError(f"jenis intervensi tidak dikenal: {intervention.type!r}")
        if intervention.type in chosen:
            raise ValueError(f"intervensi ganda untuk jenis yang sama: {intervention.type}")
        chosen[intervention.type] = intervention
    return chosen


def treated_fractions(
    cells: pd.DataFrame, interventions: list[Intervention], scenario_cfg: dict
) -> dict[str, pd.Series]:
    """Fraction of each cell's area actually touched by each intervention.

    Green roof is resolved before cool roof so the two cannot repaint the same square metre:
    cool roof gets whatever roof the green roof did not take.
    """
    chosen = _by_type(interventions)
    fractions: dict[str, pd.Series] = {}
    roof_taken = pd.Series(0.0, index=cells.index)

    if GREEN_ROOF in chosen:
        flat_share, _ = config_entry(scenario_cfg, "green_roof", "flat_roof_share")
        adoption = float(chosen[GREEN_ROOF].params[PARAM_NAME[GREEN_ROOF]])
        green = cells["roof_frac"] * float(flat_share) * adoption
        fractions[GREEN_ROOF] = green
        roof_taken = roof_taken + green

    if COOL_ROOF in chosen:
        adoption = float(chosen[COOL_ROOF].params[PARAM_NAME[COOL_ROOF]])
        available = (cells["roof_frac"] - roof_taken).clip(lower=0.0)
        fractions[COOL_ROOF] = available * adoption

    if TREE in chosen:
        requested = float(chosen[TREE].params[PARAM_NAME[TREE]]) / PERCENTAGE_POINTS
        fractions[TREE] = plantable_headroom(cells).clip(upper=requested)

    return fractions


def apply_interventions(
    cells: pd.DataFrame, interventions: list[Intervention], scenario_cfg: dict
) -> pd.DataFrame:
    """Return a NEW frame with model features moved by the interventions."""
    after = cells.copy()
    fractions = treated_fractions(cells, interventions, scenario_cfg)

    if GREEN_ROOF in fractions:
        ndvi_green, _ = config_entry(scenario_cfg, "green_roof", "ndvi_green")
        albedo_green, _ = config_entry(scenario_cfg, "green_roof", "albedo_green")
        share = fractions[GREEN_ROOF]
        # Only the greened share moves, and greenness only upward: a roof garden cannot make
        # a cell less green than it already was.
        after["ndvi"] = after["ndvi"] + share * (
            float(ndvi_green) - after["ndvi"]
        ).clip(lower=0.0)
        after["albedo"] = after["albedo"] + share * (float(albedo_green) - after["albedo"])

    if COOL_ROOF in fractions:
        albedo_cool, _ = config_entry(scenario_cfg, "cool_roof", "albedo_cool")
        albedo_base, _ = config_entry(scenario_cfg, "cool_roof", "albedo_roof_base")
        after["albedo"] = after["albedo"] + fractions[COOL_ROOF] * (
            float(albedo_cool) - float(albedo_base)
        )

    if TREE in fractions:
        ndvi_tree, _ = config_entry(scenario_cfg, "tree_planting", "ndvi_tree")
        delta = fractions[TREE]
        after["ndvi"] = after["ndvi"] + delta * (float(ndvi_tree) - after["ndvi"]).clip(lower=0.0)
        after["tree_frac"] = after["tree_frac"] + delta

    for column in BOUNDED_FEATURES:
        if column in after.columns:
            after[column] = after[column].clip(lower=0.0, upper=1.0)
    return after


def intervened_area_m2(
    cells: pd.DataFrame, interventions: list[Intervention], scenario_cfg: dict
) -> dict[str, float]:
    """Square metres treated per intervention type, from the same fractions the model saw."""
    fractions = treated_fractions(cells, interventions, scenario_cfg)
    return {itype: float(series.sum() * CELL_AREA_M2) for itype, series in fractions.items()}


def training_quantiles(frame: pd.DataFrame, percentile: float | None = None) -> pd.Series:
    """Upper bound of the training envelope, per feature.

    A scenario that pushes a feature past this is asking the model about a city it has never
    seen, so the result gets flagged rather than quietly reported.
    """
    cut = 99.0 if percentile is None else float(percentile)
    return frame[FEATURES].quantile(cut / 100.0)


def _extrapolated(after: pd.DataFrame, train_q99: pd.Series) -> tuple[str, ...]:
    return tuple(
        name for name in FEATURES
        if name in train_q99.index and after[name].max() > train_q99[name]
    )


def _population_weighted(delta: np.ndarray, pop: pd.Series) -> float:
    """Mean delta weighted by residents, falling back to the plain mean when nobody lives here.

    1_207 good cells have NaN pop, so a naive weighted mean returns NaN and the UI would
    print "NaN °C" to a planner.
    """
    weights = pop.fillna(0.0).to_numpy()
    if weights.sum() <= 0:
        return float(np.mean(delta))
    return float(np.average(delta, weights=weights))


def simulate(
    cells: pd.DataFrame,
    interventions: list[Intervention],
    booster: lgb.Booster,
    scenario_cfg: dict,
    costs_cfg: dict,
    train_q99: pd.Series,
) -> ScenarioResult:
    """Predict the cooling, the people reached, the area, and the cost for one kelurahan."""
    if cells.empty:
        raise ValueError("tidak ada sel untuk disimulasikan")
    kel_ids = cells["kel_id"].unique()
    if len(kel_ids) != 1:
        raise ValueError(f"simulate() hanya untuk satu kelurahan, dapat {len(kel_ids)}")

    after = apply_interventions(cells, interventions, scenario_cfg)
    delta = predict(booster, after) - predict(booster, cells)

    threshold, _ = config_entry(scenario_cfg, "extrapolation", "min_cooling_for_benefit_c")
    vulnerable = cells["pop_u5"].fillna(0.0) + cells["pop_65p"].fillna(0.0)
    benefiting = float(vulnerable[delta <= float(threshold)].sum())

    areas = intervened_area_m2(cells, interventions, scenario_cfg)
    cost_total = 0.0
    sources: list[str] = []
    for itype, area in areas.items():
        amount, itype_sources = intervention_cost(itype, area, costs_cfg)
        cost_total += amount
        sources.extend(itype_sources)

    flagged = _extrapolated(after, train_q99)

    return ScenarioResult(
        kel_id=str(kel_ids[0]),
        delta_lst_c=float(np.mean(delta)),
        delta_lst_pop_weighted_c=_population_weighted(delta, cells["pop"]),
        vulnerable_benefiting=benefiting,
        area_m2=float(sum(areas.values())),
        area_by_type=areas,
        cost_idr=cost_total,
        cost_sources=tuple(dict.fromkeys(sources)),
        extrapolation=bool(flagged),
        extrapolated_features=flagged,
        n_cells=len(cells),
    )
```

- [ ] **Step 6: Jalankan tes untuk memastikan lulus**

Run: `uv run pytest tests/test_scenario.py -v`
Expected: PASS, 29 tes. Butuh `model/costs.py` dari Task M3-T2; kalau belum ada, kerjakan T2 lalu kembali ke langkah ini.

- [ ] **Step 7: Commit**

```bash
git add model/scenario.py config/scenario.yaml docs/DECISIONS.md tests/test_scenario.py
git commit -m "feat: tambah mesin skenario dengan batas fisik dan flag ekstrapolasi

Luas yang dibiayai dan luas yang disimulasikan berasal dari satu fungsi yang sama,
jadi keduanya tidak mungkin berbeda.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task M3-T2: Biaya intervensi

**Files:**
- Create: `model/costs.py`
- Test: `tests/test_costs.py`

**Interfaces:**
- Consumes: `teduh_agent.store.config_entry` (M0-T3).
- Produces:
  - `CELL_AREA_M2 = 92.8 * 92.2` (= 8.556,16)
  - `COST_KEYS: dict[str, tuple[tuple[str, str], ...]]` — jenis intervensi → entri config yang dipakainya, dalam urutan sitasi
  - `trees_for_area(area_m2: float, costs_cfg: dict) -> float`
  - `intervention_cost(itype: str, area_m2: float, costs_cfg: dict) -> tuple[float, list[str]]`

**Kenapa `model/costs.py` tidak mengimpor `model/scenario.py`:** `scenario.py` butuh `intervention_cost`, jadi impor balik akan membuat siklus. Nama jenis intervensi karenanya diulang sebagai literal di `COST_KEYS`. Duplikasi tiga string itu dijaga oleh `test_cost_keys_cover_exactly_the_scenario_intervention_types`, yang gagal kalau keduanya bergeser.

- [ ] **Step 1: Tulis tes yang gagal**

Buat `tests/test_costs.py`:

```python
"""Money a city might actually spend. Every figure must trace to config/costs.yaml, and the
sourced Kepgub prices must stay distinguishable from the ASUMSI ones -- that distinction is
what docs/DECISIONS.md commits to and what pipeline/verify_costs.py polices upstream."""

import pytest

from model.costs import CELL_AREA_M2, COST_KEYS, intervention_cost, trees_for_area
from model.scenario import COOL_ROOF, GREEN_ROOF, INTERVENTION_TYPES, TREE


@pytest.fixture
def costs(fixture_store):
    return fixture_store.costs_cfg


@pytest.mark.unit
def test_cell_area_matches_the_pipeline_cell_size():
    # pipeline/build_grid.py reports the WorldPop cell as 92.8 x 92.2 m at Jakarta's
    # latitude, and pipeline/aggregate_kelurahan.py uses the same product for area_km2.
    assert CELL_AREA_M2 == pytest.approx(8_556.16)


@pytest.mark.unit
def test_cost_keys_cover_exactly_the_scenario_intervention_types():
    # Guards the deliberate string duplication that avoids a circular import.
    assert set(COST_KEYS) == set(INTERVENTION_TYPES)


@pytest.mark.integration
def test_trees_for_area_uses_the_canopy_bridge_assumption(costs):
    # canopy_m2_per_tree is 12.0, kept as a SEPARATE assumption from the sourced per-tree
    # price precisely so it stays obvious which half is official.
    assert trees_for_area(120.0, costs) == pytest.approx(10.0)


@pytest.mark.integration
def test_tree_cost_combines_the_sapling_and_the_planting_operation(costs):
    # 2_702_703 (Tabebuya, Kepgub item 696.19) + 1_950_000 (rootball handling, item 660.91).
    amount, _ = intervention_cost(TREE, 12.0, costs)
    assert amount == pytest.approx(4_652_703.0)


@pytest.mark.integration
def test_tree_cost_cites_all_three_config_entries_it_used(costs):
    _, sources = intervention_cost(TREE, 12.0, costs)
    assert len(sources) == 3
    assert any("Kepgub" in source for source in sources)
    assert "ASUMSI" in sources, "canopy_m2_per_tree adalah ASUMSI dan harus terlihat"


@pytest.mark.integration
def test_cool_roof_cost_is_per_square_metre(costs):
    amount, sources = intervention_cost(COOL_ROOF, 100.0, costs)
    assert amount == pytest.approx(9_500_000.0)
    assert sources == ["ASUMSI"]


@pytest.mark.integration
def test_green_roof_cost_is_per_square_metre(costs):
    amount, sources = intervention_cost(GREEN_ROOF, 100.0, costs)
    assert amount == pytest.approx(60_000_000.0)
    assert sources == ["ASUMSI"]


@pytest.mark.integration
def test_zero_area_costs_nothing(costs):
    for itype in INTERVENTION_TYPES:
        amount, _ = intervention_cost(itype, 0.0, costs)
        assert amount == 0.0


@pytest.mark.integration
def test_cost_scales_linearly_with_area(costs):
    small, _ = intervention_cost(COOL_ROOF, 100.0, costs)
    large, _ = intervention_cost(COOL_ROOF, 1_000.0, costs)
    assert large == pytest.approx(small * 10)


@pytest.mark.integration
def test_negative_area_is_rejected(costs):
    with pytest.raises(ValueError, match="negatif"):
        intervention_cost(COOL_ROOF, -1.0, costs)


@pytest.mark.integration
def test_unknown_intervention_is_rejected(costs):
    with pytest.raises(ValueError, match="cool_pavement"):
        intervention_cost("cool_pavement", 100.0, costs)


@pytest.mark.unit
def test_a_config_entry_without_a_source_blocks_the_cost():
    # CLAUDE.md rule 4 enforced end to end: an unattributed price never becomes a number.
    broken = {"cool_roof": {"cost_idr_per_m2": {"value": 95_000}}}
    with pytest.raises(KeyError, match="source"):
        intervention_cost(COOL_ROOF, 100.0, broken)
```

- [ ] **Step 2: Jalankan tes untuk memastikan gagal**

Run: `uv run pytest tests/test_costs.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'model.costs'`

- [ ] **Step 3: Tulis `model/costs.py`**

```python
"""Square metres to rupiah, carrying the provenance of every figure used.

Returning the sources alongside the amount is not decoration. optimize_portfolio puts a
budget figure in front of a city, and the brief validator will reject that number unless a
Fact can cite where it came from. Four prices come from Kepgub DKI 811/2025 and are verified
against the PDF text layer by pipeline/verify_costs.py; the rest are ASUMSI because a sweep
of all 2005 pages found no reflective roof coating and no growing-medium line item at all
(docs/DECISIONS.md). The caller is handed both and must not flatten the difference.

This module deliberately does NOT import model/scenario.py. scenario.py needs
intervention_cost(), so importing back would be a cycle. The intervention type names are
therefore repeated here as literals, and tests/test_costs.py asserts the two sets stay equal.
"""

from teduh_agent.store import config_entry

# WorldPop cell size at Jakarta's latitude, from pipeline/build_grid.py. Matches the
# CELL_AREA_KM2 used by pipeline/aggregate_kelurahan.py.
CELL_AREA_M2 = 92.8 * 92.2

TREE_PLANTING = "tree_planting"

# Intervention type -> the config entries its price is built from, in citation order.
COST_KEYS: dict[str, tuple[tuple[str, str], ...]] = {
    TREE_PLANTING: (
        ("tree_planting", "tree_unit_idr"),
        ("tree_planting", "planting_unit_idr"),
        ("tree_planting", "canopy_m2_per_tree"),
    ),
    "cool_roof": (("cool_roof", "cost_idr_per_m2"),),
    "green_roof": (("green_roof", "cost_idr_per_m2"),),
}


def trees_for_area(area_m2: float, costs_cfg: dict) -> float:
    """How many trees it takes to produce this much new canopy.

    canopy_m2_per_tree is the bridge between a per-tree price and CONCEPT §7.5's canopy
    percentage points. It is kept as a separate ASUMSI rather than folded into the sourced
    price, so it stays obvious which half is official and which is guessed.
    """
    canopy_per_tree, _ = config_entry(costs_cfg, "tree_planting", "canopy_m2_per_tree")
    return area_m2 / float(canopy_per_tree)


def _sources(itype: str, costs_cfg: dict) -> list[str]:
    return [config_entry(costs_cfg, *path)[1] for path in COST_KEYS[itype]]


def intervention_cost(itype: str, area_m2: float, costs_cfg: dict) -> tuple[float, list[str]]:
    """Capital cost in IDR for treating `area_m2`, plus the source of every figure used."""
    if itype not in COST_KEYS:
        raise ValueError(f"jenis intervensi tidak punya harga: {itype!r}")
    if area_m2 < 0:
        raise ValueError(f"luas tidak boleh negatif: {area_m2}")

    if itype == TREE_PLANTING:
        tree_unit, _ = config_entry(costs_cfg, "tree_planting", "tree_unit_idr")
        planting_unit, _ = config_entry(costs_cfg, "tree_planting", "planting_unit_idr")
        amount = trees_for_area(area_m2, costs_cfg) * (float(tree_unit) + float(planting_unit))
    else:
        per_m2, _ = config_entry(costs_cfg, itype, "cost_idr_per_m2")
        amount = area_m2 * float(per_m2)

    return amount, _sources(itype, costs_cfg)
```

- [ ] **Step 4: Jalankan tes untuk memastikan lulus**

Run: `uv run pytest tests/test_costs.py -v`
Expected: PASS, 12 tes.

- [ ] **Step 5: Jalankan tes skenario yang tadi tertahan**

Run: `uv run pytest tests/test_scenario.py tests/test_costs.py -v`
Expected: PASS semuanya (41 tes).

- [ ] **Step 6: Periksa kewajaran angka pada kelurahan nyata**

```bash
uv run python -c "
import lightgbm as lgb
from model.scenario import COOL_ROOF, TREE, from_level, simulate, training_quantiles
from model.train import MODEL_PATH, prepare
from teduh_agent.store import load

store = load()
frame = prepare(store.grid.reset_index())
q99 = training_quantiles(frame)
booster = lgb.Booster(model_file=str(MODEL_PATH))

for kel, nama in [('ID3173040002','Kampung Rawa'), ('ID3172030001','Pondok Ranggon')]:
    cells = frame[frame['kel_id'] == kel]
    print(f'--- {nama} ({len(cells)} sel)')
    for itype in (TREE, COOL_ROOF):
        for level in ('low','medium','high'):
            r = simulate(cells, [from_level(itype, level)], booster,
                         store.scenario_cfg, store.costs_cfg, q99)
            print(f'  {itype:14s} {level:7s} dLST {r.delta_lst_c:+6.3f} C  '
                  f'luas {r.area_m2:10,.0f} m2  Rp {r.cost_idr:16,.0f}  '
                  f'ekstrapolasi {r.extrapolation}')
"
```
Expected: semua `dLST` negatif atau nol, biaya naik seiring level, tidak ada NaN.

Kampung Rawa hampir seluruhnya terbangun, jadi luas penanaman pohonnya akan jauh lebih kecil daripada Pondok Ranggon yang `tree_frac`-nya 0,495 — itu batas fisik yang benar, bukan bug.

- [ ] **Step 7: Commit**

```bash
git add model/costs.py tests/test_costs.py
git commit -m "feat: hitung biaya intervensi dari harga bersumber, membawa provenance

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Definisi M3a selesai

- [ ] `uv run pytest tests/test_scenario.py tests/test_costs.py -q` hijau (41 tes).
- [ ] Menambah pohon atau cool roof **tidak pernah** menaikkan LST, pada ketiga level.
- [ ] Skenario absurd diberi `extrapolation: true` beserta daftar fitur yang melampaui persentil 99.
- [ ] Luas yang dibiayai persis sama dengan luas yang disimulasikan.
- [ ] `green_roof.ndvi_green` ada di `config/scenario.yaml` dengan `source: "ASUMSI"` dan tercatat di `docs/DECISIONS.md`.
- [ ] Tidak ada konstanta baru di luar `config/`.

**Selanjutnya:** [`m3-tools.md`](m3-tools.md) — tujuh tool deterministik untuk agen.
