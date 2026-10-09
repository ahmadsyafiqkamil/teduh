"""Stack the local rasters onto the WorldPop 100m grid and join kelurahan (CONCEPT §7.2).

All inputs are already on disk and pixel-aligned by pipeline/gee_extract.py, so nothing is
fetched here and Earth Engine is never touched (CLAUDE.md rule 6). WorldCover is 10x finer
and the DEM 3x finer than the target grid; both are area-averaged down with warp.reproject
rather than a naive reshape, because WorldCover's bounds are offset ~5 of its own pixels.

The no2 band is skipped: it came back zero across the whole raster, so it carries no signal
(see docs/DECISIONS.md). lst_c above LST_ARTIFACT_MAX is masked as residual cloud, not kept
as a hot roof -- those cells are more vegetated and less built than average, which no real
surface that hot could be.

Run: uv run --no-project --python 3.12 --with rasterio --with numpy --with scipy \
       --with geopandas --with pyogrio --with pyarrow python pipeline/build_grid.py
Output: data/processed/grid_features.parquet (one row per 100m cell inside DKI land)
"""

from pathlib import Path
import math

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.warp import reproject
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
GRID_REF = RAW / "worldpop" / "pop_2025.tif"  # defines the output grid (CONCEPT §7.1)
GEE = RAW / "gee" / "teduh_jakarta_gee_100m.tif"
WORLDCOVER = RAW / "worldcover" / "worldcover_2021.tif"
DEM = RAW / "dem" / "cop_dem_glo30.tif"
KELURAHAN = ROOT / "data" / "boundaries" / "kelurahan.geojson"
OUT = ROOT / "data" / "processed" / "grid_features.parquet"

# GEE bands we keep. no2 is dropped: min=max=mean=0 over the whole raster (DECISIONS.md).
GEE_BANDS = ["lst_c", "lst_n", "albedo", "ndvi", "ndbi", "ndwi", "roof_frac", "bldg_h_mean"]

# ESA WorldCover v200 legend. Jakarta only carries 10/30/40/50/80 in practice, but 90 and 95
# are folded in so the same mapping holds if the pipeline is pointed at another coastal city.
WC_TREE = (10, 95)  # tree cover, mangroves
WC_BUILT = (50,)  # built-up
WC_WATER = (80, 90)  # permanent water, herbaceous wetland

# WorldPop R2025A age bands. pop_u5 = 0-1 plus 1-4; pop_65p = 65 through 90+ (DATA_SOURCES §A).
AGE_U5 = ("00", "01")
AGE_65P = ("65", "70", "75", "80", "85", "90")

# Residual-cloud cutoff. Cells above this are 0.04% of the grid and sit at ndvi 0.32 vs 0.24
# and roof_frac 0.19 vs 0.28 citywide -- vegetated, unbuilt, and scattered across 25 specks of
# median size 2. A real surface that hot would be dark roof or asphalt, so these are artifacts.
LST_ARTIFACT_MAX = 65.0

# Below this many clear observations a cell's median is unreliable; those cells also skew hot
# (mean 45.3 C vs 41.0 citywide). 20 sits just under the 1st percentile (22). CONCEPT §14.
LST_N_LOW = 20

# Fraction of a cell that must be water before it counts as water for the coastline search.
WATER_CELL_MIN = 0.5

# NDVI of a fully wooded cell, calibrated from the data (CONCEPT §7.5). If the strict threshold
# yields too few cells to take a stable median, fall back to the loose one and record it.
CANOPY_FRAC_STRICT = 0.8
CANOPY_FRAC_LOOSE = 0.6
CANOPY_MIN_CELLS = 50

PLAUSIBLE = {
    "lst_c": (15.0, LST_ARTIFACT_MAX),
    "albedo": (0.0, 0.8),
    "ndvi": (-1.0, 1.0),
    "ndbi": (-1.0, 1.0),
    "ndwi": (-1.0, 1.0),
    "tree_frac": (0.0, 1.0),
    "built_frac": (0.0, 1.0),
    "water_frac": (0.0, 1.0),
    "roof_frac": (0.0, 1.0),
    "bldg_h_mean": (0.0, 100.0),
    # Below sea level is real here, not an artifact: the 4 deepest cells (to -11.6 m) are all in
    # Danau Sunter, North Jakarta -- 3.2 km inland, built_frac 1.0, populated. That is the city's
    # textbook land-subsidence zone, kept dry by dikes, and exactly the kind of cell this project
    # must not throw away. Pluit's -3.5 m cells are the reservoir surface (water_frac 1.0).
    "elev_m": (-15.0, 200.0),
    "dist_coast_km": (0.0, 100.0),
}

M_PER_DEG_LAT = 111_320.0  # mean meridional metres per degree, ample for a km-scale distance


def _read_masked(path: Path, band: int = 1) -> np.ndarray:
    """Read one band as float64 with nodata turned into NaN.

    WorldPop ships nodata as -99999.0 rather than NaN, so a plain isfinite() check lets it
    through and wrecks every sum. Going through the mask is the only safe route.
    """
    with rasterio.open(path) as src:
        return src.read(band, masked=True).astype("float64").filled(np.nan)


def _downsample(
    path: Path, ref: rasterio.io.DatasetReader, values: tuple[int, ...] | None = None
) -> np.ndarray:
    """Area-average a finer raster onto the reference grid.

    With `values`, the source is first turned into a 0/1 membership mask, so the average comes
    out as the fraction of the coarse cell covered by those classes.
    """
    dst = np.full(ref.shape, np.nan, dtype="float64")
    with rasterio.open(path) as src:
        band = src.read(1)
        if values is not None:
            source = np.isin(band, values).astype("float64")
        else:
            source = np.ma.masked_equal(band, src.nodata).astype("float64").filled(np.nan)
        reproject(
            source=source,
            destination=dst,
            src_transform=src.transform,
            src_crs=src.crs,
            dst_transform=ref.transform,
            dst_crs=ref.crs,
            resampling=Resampling.average,
            src_nodata=np.nan,
            dst_nodata=np.nan,
        )
    return dst


def _dist_to_sea_km(water_frac: np.ndarray, ref: rasterio.io.DatasetReader) -> np.ndarray:
    """Kilometres to Jakarta Bay, measured from the sea only and not from rivers or reservoirs.

    A plain WorldCover water mask lumps the Ciliwung and the Pluit reservoirs in with the bay,
    which would hand inland cells a near-zero distance. The bay is isolated as the largest
    connected water body touching the raster's north edge.
    """
    water = np.nan_to_num(water_frac, nan=0.0) > WATER_CELL_MIN
    labels, count = ndimage.label(water)
    if count == 0:
        raise SystemExit("tidak ada sel air sama sekali; cek mask WorldCover")

    north_edge = labels[0, :]
    north_labels = set(north_edge[north_edge > 0].tolist())
    if not north_labels:
        raise SystemExit("tepi utara raster tidak menyentuh air; Teluk Jakarta tidak terdeteksi")
    sea_label = max(north_labels, key=lambda lb: int((labels == lb).sum()))
    sea = labels == sea_label

    mid_lat = ref.transform.f + ref.transform.e * (ref.height / 2)
    m_lat = abs(ref.transform.e) * M_PER_DEG_LAT
    m_lon = abs(ref.transform.a) * M_PER_DEG_LAT * math.cos(math.radians(mid_lat))
    dist_m = ndimage.distance_transform_edt(~sea, sampling=(m_lat, m_lon))
    print(f"  Teluk Jakarta: {int(sea.sum())} sel laut dari {int(water.sum())} sel air "
          f"({count} badan air terpisah), sel {m_lat:.1f} x {m_lon:.1f} m")
    return dist_m / 1000.0


def _report_ndvi_tree(out) -> None:
    """Print the calibrated NDVI of a wooded cell, for config/scenario.yaml (CONCEPT §7.5)."""
    strict = out.loc[out["tree_frac"] > CANOPY_FRAC_STRICT, "ndvi"].dropna()
    if strict.empty:
        print(f"ndvi_tree: 0 sel tree_frac>{CANOPY_FRAC_STRICT}")
    else:
        print(f"ndvi_tree: {len(strict)} sel tree_frac>{CANOPY_FRAC_STRICT}, "
              f"median NDVI {strict.median():.4f}")
    if len(strict) >= CANOPY_MIN_CELLS:
        return
    loose = out.loc[out["tree_frac"] > CANOPY_FRAC_LOOSE, "ndvi"].dropna()
    print(f"  PERINGATAN: < {CANOPY_MIN_CELLS} sel. Ambang {CANOPY_FRAC_LOOSE} memberi "
          f"{len(loose)} sel, median {loose.median():.4f}. Catat pilihannya di docs/DECISIONS.md.")


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    ref = rasterio.open(GRID_REF)

    with rasterio.open(GEE) as src:
        if src.transform != ref.transform or src.shape != ref.shape:
            raise SystemExit("grid GEE tidak identik dengan pop_2025.tif; jalankan gee_extract ulang")
        gee_index = {name: i + 1 for i, name in enumerate(src.descriptions)}
    cols = {name: _read_masked(GEE, gee_index[name]) for name in GEE_BANDS}

    n_hot = int(np.nansum(cols["lst_c"] > LST_ARTIFACT_MAX))
    cols["lst_c"] = np.where(cols["lst_c"] > LST_ARTIFACT_MAX, np.nan, cols["lst_c"])
    print(f"lst_c     : {n_hot} sel >{LST_ARTIFACT_MAX:.0f}C di-mask sebagai sisa awan")

    cols["tree_frac"] = _downsample(WORLDCOVER, ref, WC_TREE)
    cols["built_frac"] = _downsample(WORLDCOVER, ref, WC_BUILT)
    cols["water_frac"] = _downsample(WORLDCOVER, ref, WC_WATER)
    cols["elev_m"] = _downsample(DEM, ref)
    print(f"worldcover: tree {np.nanmean(cols['tree_frac']):.3f} "
          f"built {np.nanmean(cols['built_frac']):.3f} "
          f"water {np.nanmean(cols['water_frac']):.3f}")

    cols["pop"] = _read_masked(GRID_REF)
    cols["pop_u5"] = sum(_read_masked(RAW / "worldpop" / f"age_t_{k}_2025.tif") for k in AGE_U5)
    cols["pop_65p"] = sum(_read_masked(RAW / "worldpop" / f"age_t_{k}_2025.tif") for k in AGE_65P)

    cols["dist_coast_km"] = _dist_to_sea_km(cols["water_frac"], ref)

    n_rows, n_cols = ref.shape
    rr, cc = np.meshgrid(np.arange(n_rows), np.arange(n_cols), indexing="ij")
    frame = {"cell_id": (rr * n_cols + cc).ravel()}
    for name, arr in cols.items():
        frame[name] = arr.ravel()

    xs = ref.transform.c + ref.transform.a * (cc.ravel() + 0.5)
    ys = ref.transform.f + ref.transform.e * (rr.ravel() + 0.5)
    grid = gpd.GeoDataFrame(frame, geometry=gpd.points_from_xy(xs, ys), crs=ref.crs)

    # A cell with neither population nor a thermal reading carries nothing the model can use.
    grid = grid[np.isfinite(grid["pop"]) | np.isfinite(grid["lst_c"])]

    kel = gpd.read_file(KELURAHAN)
    joined = gpd.sjoin(
        grid,
        kel[["kel_id", "kel_name", "kec_id", "kota_id", "geometry"]],
        how="inner",
        predicate="within",
    ).drop(columns=["index_right"])
    print(f"join      : {len(grid)} sel kandidat -> {len(joined)} sel di dalam DKI daratan")

    joined["lst_quality"] = np.where(joined["lst_n"] < LST_N_LOW, "low", "good")
    joined["lon"] = joined.geometry.x
    joined["lat"] = joined.geometry.y
    out = joined.drop(columns="geometry").reset_index(drop=True)
    out.to_parquet(OUT, index=False)
    print(f"wrote {OUT.relative_to(ROOT)} ({len(out)} rows, {len(out.columns)} cols)")

    _report_ndvi_tree(out)
    check(out)


def check(out) -> None:
    """Every column plausible, every cell inside a known kelurahan, vulnerable <= total pop."""
    assert len(out) > 10_000, f"terlalu sedikit sel: {len(out)}"
    kel_ids = set(gpd.read_file(KELURAHAN)["kel_id"])
    assert set(out["kel_id"]) <= kel_ids, "ada kel_id di luar kelurahan.geojson"
    print(f"  kelurahan terwakili: {out['kel_id'].nunique()} dari {len(kel_ids)}")

    for name, (lo, hi) in PLAUSIBLE.items():
        series = out[name].dropna()
        assert not series.empty, f"{name} kosong total"
        assert series.min() >= lo and series.max() <= hi, (
            f"{name} di luar rentang: {series.min():.3f}..{series.max():.3f}, harap {lo}..{hi}"
        )

    vulnerable = (out["pop_u5"] + out["pop_65p"]).dropna()
    assert (vulnerable <= out.loc[vulnerable.index, "pop"] + 1e-6).all(), (
        "pop_u5 + pop_65p melebihi pop di sebagian sel"
    )

    # The bay sits at the north edge, so coastal cells must read ~0 and the far south far more.
    assert out["dist_coast_km"].min() < 1.0, "tidak ada sel di tepi pantai"
    north = out.nlargest(200, "lat")["dist_coast_km"].mean()
    south = out.nsmallest(200, "lat")["dist_coast_km"].mean()
    assert south > north, (
        f"jarak ke pantai tidak naik ke selatan: utara {north:.1f} selatan {south:.1f}"
    )
    print(f"  dist_coast_km: utara {north:.1f} km, selatan {south:.1f} km")
    print(f"  pop total {out['pop'].sum():,.0f} (Dukcapil DKI Sem-I 2025 = 11.010.514)")
    print(f"  lst_quality low: {(out['lst_quality'] == 'low').sum()} sel")
    print("check ok")


if __name__ == "__main__":
    main()
