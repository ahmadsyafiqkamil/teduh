"""Extract Earth Engine bands for Jakarta onto the WorldPop 100m grid.

Offline step (CLAUDE.md rule 6): Earth Engine is never called at runtime.
Output grid is pixel-identical to data/raw/worldpop/pop_2025.tif, so build_grid.py
can stack the local rasters (WorldPop, WorldCover, DEM) without resampling.

Uses a batch export task via Drive: the three-dry-season Sentinel-2 median exceeds the
interactive compute budget, and the synchronous download path hangs rather than failing.
The Drive file is deleted once it has been saved locally; the folder is left behind.

Run: uv run --no-project --python 3.12 --with earthengine-api --with rasterio --with numpy \
       python -u pipeline/gee_extract.py
"""

from pathlib import Path
import os
import time

import ee
import numpy as np
import rasterio
from googleapiclient.discovery import build as build_service

ROOT = Path(__file__).resolve().parents[1]
GRID_REF = ROOT / "data" / "raw" / "worldpop" / "pop_2025.tif"
OUT = ROOT / "data" / "raw" / "gee" / "jakarta_gee_100m.tif"

DRY_SEASON = (6, 9)  # Jun-Sep, CONCEPT §7.2
YEARS = ("2023-01-01", "2026-01-01")
BUILDINGS_YEAR = ("2023-01-01", "2024-01-01")  # Open Buildings Temporal ends 2023
CLOUD_SCORE_CLEAR = 0.6  # Cloud Score+ 'cs' threshold
BUILDING_PRESENCE_THRESHOLD = 0.5  # CONCEPT §7.2; model confidence is uncalibrated

# Liang (2001) broadband shortwave albedo, OLI band mapping
ALBEDO_WEIGHTS = {"SR_B2": 0.356, "SR_B4": 0.130, "SR_B5": 0.373, "SR_B6": 0.085, "SR_B7": 0.072}
ALBEDO_OFFSET = -0.0018
ALBEDO_DIVISOR = 1.016

BANDS = ["lst_c", "lst_n", "albedo", "ndvi", "ndbi", "ndwi", "roof_frac", "bldg_h_mean", "no2"]

EXPORT_NAME = "teduh_jakarta_gee_100m"
DRIVE_FOLDER = "teduh_ee_export"
POLL_SECONDS = 20
MAX_WAIT_SECONDS = 3600
DONE_STATES = {"COMPLETED", "FAILED", "CANCELLED", "CANCEL_REQUESTED"}

PLAUSIBLE_RANGE = {
    "lst_c": (15.0, 65.0),
    "albedo": (0.0, 0.8),
    "ndvi": (-1.0, 1.0),
    "ndbi": (-1.0, 1.0),
    "ndwi": (-1.0, 1.0),
    "roof_frac": (0.0, 1.0),
    "bldg_h_mean": (0.0, 100.0),
}


def _mask_landsat(img: ee.Image) -> ee.Image:
    """Drop dilated cloud, cirrus, cloud and cloud-shadow pixels via QA_PIXEL bits 1-4."""
    clear = img.select("QA_PIXEL").bitwiseAnd(0b11110).eq(0)
    return img.updateMask(clear)


def _landsat_thermal_optical() -> tuple[ee.Image, ee.Image, ee.Image]:
    """Dry-season median LST (deg C), valid-observation count, and broadband albedo."""
    col = (
        ee.ImageCollection("LANDSAT/LC08/C02/T1_L2")
        .merge(ee.ImageCollection("LANDSAT/LC09/C02/T1_L2"))
        .filterDate(*YEARS)
        .filter(ee.Filter.calendarRange(*DRY_SEASON, "month"))
        .map(_mask_landsat)
    )

    lst = col.map(
        lambda i: i.select("ST_B10").multiply(0.00341802).add(149.0).subtract(273.15).rename("lst_c")
    )

    def albedo(img: ee.Image) -> ee.Image:
        sr = img.select(list(ALBEDO_WEIGHTS)).multiply(0.0000275).add(-0.2)
        total = ee.Image(0)
        for band, weight in ALBEDO_WEIGHTS.items():
            total = total.add(sr.select(band).multiply(weight))
        return total.add(ALBEDO_OFFSET).divide(ALBEDO_DIVISOR).rename("albedo")

    return (
        lst.median().rename("lst_c"),
        lst.count().rename("lst_n"),
        col.map(albedo).median().rename("albedo"),
    )


def _sentinel2_indices() -> ee.Image:
    """Dry-season median NDVI, NDBI and NDWI from Sentinel-2, masked with Cloud Score+."""
    s2 = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterDate(*YEARS)
        .filter(ee.Filter.calendarRange(*DRY_SEASON, "month"))
        .linkCollection(ee.ImageCollection("GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED"), ["cs"])
        .map(lambda i: i.updateMask(i.select("cs").gte(CLOUD_SCORE_CLEAR)))
    )

    def indices(img: ee.Image) -> ee.Image:
        return ee.Image.cat(
            img.normalizedDifference(["B8", "B4"]).rename("ndvi"),
            img.normalizedDifference(["B11", "B8"]).rename("ndbi"),
            img.normalizedDifference(["B3", "B8"]).rename("ndwi"),
        )

    return s2.map(indices).median()


def _buildings() -> ee.Image:
    """Roof fraction and mean building height.

    Both are cell means over 4m pixels: roof_frac is the share of the cell flagged as
    building, while bldg_h_mean averages height across the whole cell (zeros included),
    so it reads as a bulk proxy, not the mean height of the buildings themselves.
    """
    img = (
        ee.ImageCollection("GOOGLE/Research/open-buildings-temporal/v1")
        .filterDate(*BUILDINGS_YEAR)
        .mosaic()
    )
    roof = img.select("building_presence").gt(BUILDING_PRESENCE_THRESHOLD).rename("roof_frac")
    return ee.Image.cat(roof, img.select("building_height").rename("bldg_h_mean"))


def _no2() -> ee.Image:
    return (
        ee.ImageCollection("COPERNICUS/S5P/OFFL/L3_NO2")
        .filterDate(*YEARS)
        .filter(ee.Filter.calendarRange(*DRY_SEASON, "month"))
        .select("tropospheric_NO2_column_number_density")
        .mean()
        .rename("no2")
    )


def build_image() -> ee.Image:
    lst, lst_n, albedo = _landsat_thermal_optical()
    return ee.Image.cat(
        lst, lst_n, albedo, _sentinel2_indices(), _buildings(), _no2()
    ).select(BANDS).toFloat()


def grid_spec() -> dict:
    """Read crs, geotransform and size from the WorldPop reference raster."""
    with rasterio.open(GRID_REF) as src:
        t = src.transform
        return {
            "crs": str(src.crs),
            "crs_transform": [t.a, t.b, t.c, t.d, t.e, t.f],
            "dimensions": f"{src.width}x{src.height}",
        }


def start_export(image: ee.Image, spec: dict) -> ee.batch.Task:
    task = ee.batch.Export.image.toDrive(
        image=image,
        description=EXPORT_NAME,
        folder=DRIVE_FOLDER,
        fileNamePrefix=EXPORT_NAME,
        crs=spec["crs"],
        crsTransform=spec["crs_transform"],
        dimensions=spec["dimensions"],
        fileFormat="GeoTIFF",
        maxPixels=int(1e9),
    )
    task.start()
    print(f"export task {task.id} started")
    return task


def wait_for(task: ee.batch.Task) -> None:
    """Poll until the task settles, printing each state change."""
    started = time.monotonic()
    last_state = None
    while True:
        status = task.status()
        state = status["state"]
        if state != last_state:
            print(f"  {state} (+{int(time.monotonic() - started)}s)")
            last_state = state
        if state in DONE_STATES:
            break
        if time.monotonic() - started > MAX_WAIT_SECONDS:
            raise TimeoutError(f"task {task.id} still {state} after {MAX_WAIT_SECONDS}s")
        time.sleep(POLL_SECONDS)
    if state != "COMPLETED":
        raise RuntimeError(f"export {state}: {status.get('error_message', '(no message)')}")


def fetch_from_drive(filename: str, dest: Path) -> None:
    """Download the exported file, then remove it from Drive."""
    drive = build_service("drive", "v3", credentials=ee.data.get_persistent_credentials())
    found = (
        drive.files()
        .list(q=f"name = '{filename}' and trashed = false", fields="files(id, size)")
        .execute()
        .get("files", [])
    )
    if not found:
        raise FileNotFoundError(f"{filename} not found in Drive")
    if len(found) > 1:
        raise RuntimeError(f"{len(found)} copies of {filename} in Drive; remove the stale ones")

    file_id = found[0]["id"]
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(drive.files().get_media(fileId=file_id).execute())
    drive.files().delete(fileId=file_id).execute()
    print(f"wrote {dest.relative_to(ROOT)} ({dest.stat().st_size / 1e6:.1f} MB), Drive copy deleted")


def verify(path: Path) -> None:
    """Fail loudly if band scaling or masking went wrong."""
    with rasterio.open(path) as src:
        assert src.count == len(BANDS), f"expected {len(BANDS)} bands, got {src.count}"
        for index, name in enumerate(BANDS, start=1):
            values = src.read(index)
            values = values[np.isfinite(values) & (values != 0)]
            assert values.size, f"{name}: no valid pixels"
            low, high = float(values.min()), float(values.max())
            print(f"  {name}: min={low:.3f} max={high:.3f} mean={float(values.mean()):.3f}")
            if name in PLAUSIBLE_RANGE:
                expected_low, expected_high = PLAUSIBLE_RANGE[name]
                assert expected_low <= low and high <= expected_high, (
                    f"{name} outside {PLAUSIBLE_RANGE[name]}: [{low:.3f}, {high:.3f}]"
                )
    print("verify OK")


def main() -> None:
    project = os.environ.get("TEDUH_EE_PROJECT") or os.environ.get("GOOGLE_CLOUD_PROJECT")
    ee.Initialize(project=project) if project else ee.Initialize()

    spec = grid_spec()
    print(f"grid: {spec['dimensions']} {spec['crs']}")

    wait_for(start_export(build_image(), spec))
    fetch_from_drive(f"{EXPORT_NAME}.tif", OUT)
    verify(OUT)


if __name__ == "__main__":
    main()
