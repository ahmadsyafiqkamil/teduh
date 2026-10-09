"""Roll the 100m grid up to kelurahan and compute the Heat Vulnerability Index (CONCEPT §7.4).

Cells are near enough equal-area on this grid that an unweighted mean IS the area-weighted
mean, so only the exposure metric gets a population weighting -- that distinction matters
because a kelurahan's hottest corner is not always where its people are.

HVI components are within-city percentiles, so every figure here is relative to Jakarta and
must never be read as an absolute risk. Weights come from config/hvi.yaml and are a policy
choice, not a measurement.

Cells flagged lst_quality == "low" are dropped from the thermal statistics but kept in the
population totals: their LST median is unreliable, but their residents are real.

Run: uv run --no-project --python 3.12 --with pandas --with pyarrow --with numpy --with pyyaml \
       python pipeline/aggregate_kelurahan.py
Output: data/processed/kelurahan_metrics.parquet (one row per kelurahan)
"""

from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from model.hvi import components, hvi, load_weights, percentile, rank

ROOT = Path(__file__).resolve().parents[1]
GRID = ROOT / "data" / "processed" / "grid_features.parquet"
HVI_CONFIG = ROOT / "config" / "hvi.yaml"
OUT = ROOT / "data" / "processed" / "kelurahan_metrics.parquet"

# pipeline/build_grid.py reports the WorldPop cell as 92.8 x 92.2 m at Jakarta's latitude.
CELL_AREA_KM2 = (92.8 * 92.2) / 1_000_000

# Features averaged plainly over a kelurahan's cells.
AREA_MEANS = ["lst_c", "albedo", "ndvi", "ndbi", "ndwi",
              "tree_frac", "built_frac", "water_frac", "roof_frac",
              "bldg_h_mean", "elev_m", "dist_coast_km"]

# Headcounts, summed.
POP_SUMS = ["pop", "pop_u5", "pop_65p"]


def _pop_weighted_lst(good: pd.DataFrame) -> pd.Series:
    """Mean LST weighted by residents: what the average person feels, not the average hectare."""
    frame = good.dropna(subset=["lst_c", "pop"]).copy()
    frame["_wsum"] = frame["lst_c"] * frame["pop"]
    totals = frame.groupby("kel_id")[["_wsum", "pop"]].sum()
    return (totals["_wsum"] / totals["pop"].replace(0, np.nan)).rename("lst_c_pop_weighted")


def main() -> None:
    cfg = yaml.safe_load(HVI_CONFIG.read_text())
    weights = load_weights(cfg)
    hazard_min = cfg["exposed_vulnerable"]["hazard_percentile_min"]["value"]

    grid = pd.read_parquet(GRID)
    good = grid[grid["lst_quality"] == "good"]
    print(f"grid      : {len(grid)} sel, {len(grid) - len(good)} dibuang dari statistik termal")

    # Cell-level hazard percentile, for the headcount metric CONCEPT §7.4 defines on cells.
    grid["cell_h"] = percentile(grid["lst_c"].where(grid["lst_quality"] == "good"))
    grid["vulnerable"] = grid["pop_u5"] + grid["pop_65p"]
    exposed = (
        grid.loc[grid["cell_h"] >= hazard_min]
        .groupby("kel_id")["vulnerable"].sum()
        .rename("exposed_vulnerable")
    )

    names = grid.groupby("kel_id")[["kel_name", "kec_id", "kota_id"]].first()
    thermal = good.groupby("kel_id")[AREA_MEANS].mean().add_suffix("_mean")
    people = grid.groupby("kel_id")[POP_SUMS].sum()
    n_cells = grid.groupby("kel_id").size().rename("n_cells")

    kel = pd.concat([names, thermal, people, n_cells, _pop_weighted_lst(good), exposed], axis=1)
    kel["exposed_vulnerable"] = kel["exposed_vulnerable"].fillna(0.0)
    kel["area_km2"] = kel["n_cells"] * CELL_AREA_KM2
    kel["pop_density"] = kel["pop"] / kel["area_km2"]
    kel["vulnerable_share"] = (kel["pop_u5"] + kel["pop_65p"]) / kel["pop"].replace(0, np.nan)

    city_lst = good["lst_c"].mean()
    kel["lst_anomaly_c"] = kel["lst_c_mean"] - city_lst
    print(f"kota      : LST rata-rata {city_lst:.2f} C")

    comp = components(kel)
    kel[list(comp.columns)] = comp
    kel["hvi"] = hvi(comp, weights)
    kel["hvi_rank"] = rank(kel["hvi"])

    out = kel.reset_index()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(OUT, index=False)
    print(f"wrote {OUT.relative_to(ROOT)} ({len(out)} rows, {len(out.columns)} cols)")

    print("\n10 kelurahan prioritas (HVI tertinggi):")
    print(f"  {'#':>2s} {'kelurahan':22s} {'kota':7s} {'HVI':>5s} {'LST':>6s} {'anom':>6s} "
          f"{'pohon':>6s} {'rentan':>8s}")
    for _, r in out.nsmallest(10, "hvi_rank").iterrows():
        print(f"  {r['hvi_rank']:2d} {r['kel_name'][:22]:22s} {r['kota_id']:7s} "
              f"{r['hvi']:5.3f} {r['lst_c_mean']:6.2f} {r['lst_anomaly_c']:+6.2f} "
              f"{r['tree_frac_mean']:6.3f} {r['exposed_vulnerable']:8,.0f}")

    check(out, grid)


def check(out: pd.DataFrame, grid: pd.DataFrame) -> None:
    """HVI bounded, every kelurahan present, headcounts conserved from the grid."""
    assert len(out) == grid["kel_id"].nunique(), (
        f"{len(out)} kelurahan di output vs {grid['kel_id'].nunique()} di grid"
    )
    for col in ("H", "E", "S", "A", "hvi"):
        series = out[col].dropna()
        assert not series.empty, f"{col} kosong total"
        assert series.between(0.0, 1.0).all(), (
            f"{col} di luar [0,1]: {series.min():.3f}..{series.max():.3f}"
        )

    assert np.isclose(out["pop"].sum(), grid["pop"].sum()), "total penduduk tidak lestari"
    assert (out["exposed_vulnerable"] <= out["pop_u5"] + out["pop_65p"] + 1e-6).all(), (
        "warga rentan terpapar melebihi total warga rentan di kelurahan"
    )
    assert out["hvi_rank"].min() == 1 and out["hvi_rank"].max() <= len(out), "peringkat HVI rusak"

    # A bare, dense kelurahan must outrank a leafy one, or a component has the wrong sign.
    leafy = out.nlargest(20, "tree_frac_mean")["hvi"].mean()
    bare = out.nsmallest(20, "tree_frac_mean")["hvi"].mean()
    assert bare > leafy, (
        f"HVI tidak lebih tinggi di kelurahan gundul: gundul {bare:.3f} rimbun {leafy:.3f}"
    )
    print(f"\n  HVI rata-rata: 20 terrimbun {leafy:.3f} vs 20 tergundul {bare:.3f}")
    print(f"  warga rentan terpapar (H>=0,8): {out['exposed_vulnerable'].sum():,.0f} jiwa")
    print("check ok")


if __name__ == "__main__":
    main()
