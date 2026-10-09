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
