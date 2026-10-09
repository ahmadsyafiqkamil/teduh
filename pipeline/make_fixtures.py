"""Cut a small, committed test fixture out of the full grid (CLAUDE.md M1).

grid_features.parquet is 7 MB and gitignored, so the M2-M4 tests cannot depend on it. This
carves out three kelurahan spanning the HVI range and writes them to tests/fixtures/, which IS
committed, so the scenario, provenance and optimiser tests run on a fresh clone with no
pipeline run and no Earth Engine access.

The three are picked deliberately, not at random: one high-HVI kelurahan with almost no canopy
(where tree planting has room to act), one mid-range, and one leafy low-HVI one (where it does
not). A fixture drawn from one end only would let a scenario bug through -- for instance a
canopy increase that is never capped by available land.

Run: uv run --no-project --python 3.12 --with pandas --with pyarrow python pipeline/make_fixtures.py
Output: tests/fixtures/grid_features_sample.parquet, tests/fixtures/kelurahan_metrics_sample.parquet
"""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
GRID = ROOT / "data" / "processed" / "grid_features.parquet"
METRICS = ROOT / "data" / "processed" / "kelurahan_metrics.parquet"
OUT_DIR = ROOT / "tests" / "fixtures"

# Selection is by CANOPY, not by HVI rank. Those two correlate at only -0.686, so the lowest
# HVI kelurahan is not the leafiest: rank 264 is Marunda, whose HVI is low because it is coastal
# and sparsely populated (tree_frac 0.054). Picking by canopy also happens to spread HVI wide,
# because of that correlation, so one criterion buys both.
N_KELURAHAN = 3

# Cells per kelurahan. Enough for a percentile or a group-by to mean something, small enough
# that the committed file stays trivial.
CELLS_PER_KELURAHAN = 70

# Below these the fixture has lost the contrast it exists to provide. Canopy spread drives the
# scenario tests, HVI spread the optimiser and equity-constraint tests.
MIN_TREE_FRAC_SPREAD = 0.2
MIN_HVI_SPREAD = 0.3


def _pick_by_canopy(metrics: pd.DataFrame) -> pd.DataFrame:
    """The barest, the median and the leafiest kelurahan, in that order."""
    median = metrics["tree_frac_mean"].median()
    middle = (metrics["tree_frac_mean"] - median).abs().idxmin()
    picks = [
        metrics["tree_frac_mean"].idxmin(),
        middle,
        metrics["tree_frac_mean"].idxmax(),
    ]
    chosen = metrics.loc[picks].sort_values("tree_frac_mean")
    assert len(chosen) == N_KELURAHAN, (
        f"{len(chosen)} kelurahan terpilih, bukan {N_KELURAHAN}; ada peringkat kembar?"
    )
    return chosen


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    grid = pd.read_parquet(GRID)
    metrics = pd.read_parquet(METRICS)

    chosen = _pick_by_canopy(metrics)

    samples = []
    print(f"  {'#':>3s} {'kelurahan':22s} {'HVI':>5s} {'pohon':>6s} {'LST':>6s} {'sel':>5s}")
    for _, row in chosen.iterrows():
        cells = grid[grid["kel_id"] == row["kel_id"]]
        # Deterministic: take the cells with the most thermal observations, so the fixture is
        # stable across runs and biased toward good data rather than toward a random seed.
        take = cells.nlargest(CELLS_PER_KELURAHAN, "lst_n")
        samples.append(take)
        print(f"  {row['hvi_rank']:3d} {row['kel_name'][:22]:22s} {row['hvi']:5.3f} "
              f"{row['tree_frac_mean']:6.3f} {row['lst_c_mean']:6.2f} {len(take):5d}")

    sample_grid = pd.concat(samples).reset_index(drop=True)
    sample_metrics = chosen.reset_index(drop=True)

    grid_out = OUT_DIR / "grid_features_sample.parquet"
    metrics_out = OUT_DIR / "kelurahan_metrics_sample.parquet"
    sample_grid.to_parquet(grid_out, index=False)
    sample_metrics.to_parquet(metrics_out, index=False)
    print(f"wrote {grid_out.relative_to(ROOT)} ({len(sample_grid)} rows, "
          f"{grid_out.stat().st_size / 1024:.0f} KB)")
    print(f"wrote {metrics_out.relative_to(ROOT)} ({len(sample_metrics)} rows)")

    check(sample_grid, sample_metrics, grid)


def check(sample_grid: pd.DataFrame, sample_metrics: pd.DataFrame, grid: pd.DataFrame) -> None:
    """Same columns as the parent, and genuinely spanning the canopy range."""
    assert list(sample_grid.columns) == list(grid.columns), (
        "kolom fixture beda dari grid induk; tes akan lolos padahal skemanya berubah"
    )
    assert sample_grid["kel_id"].nunique() == N_KELURAHAN, "jumlah kelurahan fixture salah"
    assert sample_grid["lst_c"].notna().any(), "fixture tanpa satu pun LST valid"

    # The point of the fixture is contrast; if either spread collapses it has stopped working.
    canopy = sample_metrics["tree_frac_mean"].max() - sample_metrics["tree_frac_mean"].min()
    hvi = sample_metrics["hvi"].max() - sample_metrics["hvi"].min()
    assert canopy > MIN_TREE_FRAC_SPREAD, (
        f"rentang tree_frac fixture cuma {canopy:.3f}; tidak cukup kontras untuk uji skenario"
    )
    assert hvi > MIN_HVI_SPREAD, (
        f"rentang HVI fixture cuma {hvi:.3f}; tidak cukup kontras untuk uji optimasi/keadilan"
    )
    print(f"  rentang fixture: tree_frac {canopy:.3f}, HVI {hvi:.3f}")
    print("check ok")


if __name__ == "__main__":
    main()
