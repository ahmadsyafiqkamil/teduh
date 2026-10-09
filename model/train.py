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

from model.config import good_cells

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
