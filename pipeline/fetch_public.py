"""Download public, no-login datasets listed in docs/DATA_SOURCES.md and clip them to Jakarta.

Run: uv run --with geopandas --with pyogrio --with rasterio python pipeline/fetch_public.py

Earth Engine composites (Landsat LST, Sentinel-2 indices, Open Buildings) are NOT here;
they need EE auth and are built in pipeline/gee_extract.py.
"""

from pathlib import Path
import urllib.request

import geopandas as gpd
import rasterio
from rasterio.windows import from_bounds

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
BOUNDARIES = ROOT / "data" / "boundaries"

HDX_GDB_URL = (
    "https://data.humdata.org/dataset/84a1d98a-790b-4d66-9d14-bbfa48500802/resource/"
    "c740a308-0a63-46d6-ab15-b041e62eff58/download/idn_admin_boundaries.gdb.zip"
)
DKI_PCODE = "ID31"
KEP_SERIBU_PCODE = "ID3101"  # Kabupaten Administrasi Kepulauan Seribu, excluded (CONCEPT §7.1)
BBOX_BUFFER_DEG = 0.01

WORLDPOP = "https://data.worldpop.org/GIS"
WP_POP = f"{WORLDPOP}/Population/Global_2015_2030/R2025A/2025/IDN/v1/100m/constrained/idn_pop_2025_CN_100m_R2025A_v1.tif"
WP_AGE = f"{WORLDPOP}/AgeSex_structures/Global_2015_2030/R2025A/2025/IDN/v1/100m/constrained/idn_t_{{age:02d}}_2025_CN_100m_R2025A_v1.tif"
WP_AGES_U5 = (0, 1)
WP_AGES_65P = (65, 70, 75, 80, 85, 90)

WORLDCOVER = "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_S09E105_Map.tif"
COP_DEM = (
    "https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_S07_00_E106_00_DEM/"
    "Copernicus_DSM_COG_10_S07_00_E106_00_DEM.tif"
)
PERGUB_SHS_2026 = (
    "https://jnnqvmfhkqwfdlzevfao.supabase.co/storage/v1/object/public/regulation-pdfs/"
    "pergub-prov-dki-jakarta-no-17-tahun-2025.pdf"
)


def download(url: str, dest: Path) -> Path:
    if dest.exists():
        print(f"skip (exists) {dest.relative_to(ROOT)}")
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": "teduh-pipeline"})
    with urllib.request.urlopen(req, timeout=300) as r, open(tmp, "wb") as f:
        while chunk := r.read(1 << 20):
            f.write(chunk)
    tmp.rename(dest)
    print(f"downloaded {dest.relative_to(ROOT)} ({dest.stat().st_size / 1e6:.1f} MB)")
    return dest


def build_kelurahan() -> gpd.GeoDataFrame:
    gdb = download(HDX_GDB_URL, RAW / "hdx" / "idn_admin_boundaries.gdb.zip")
    gdf = gpd.read_file(gdb, layer="idn_admin4", where=f"adm1_pcode = '{DKI_PCODE}'")
    gdf = gdf[gdf["adm2_pcode"] != KEP_SERIBU_PCODE]
    out = gdf.rename(
        columns={
            "adm4_pcode": "kel_id", "adm4_name": "kel_name",
            "adm3_pcode": "kec_id", "adm3_name": "kec_name",
            "adm2_pcode": "kota_id", "adm2_name": "kota_name",
        }
    )[["kel_id", "kel_name", "kec_id", "kec_name", "kota_id", "kota_name", "geometry"]].to_crs(4326)
    BOUNDARIES.mkdir(parents=True, exist_ok=True)
    out.to_file(BOUNDARIES / "kelurahan.geojson", driver="GeoJSON")
    print(f"kelurahan.geojson: {len(out)} kelurahan, {out['kota_name'].nunique()} kota")
    return out


def clip_remote(url: str, bounds: tuple[float, float, float, float], dest: Path) -> None:
    """Windowed read over HTTP (GDAL /vsicurl/), so only the Jakarta part is fetched.

    Servers without HTTP range support (WorldPop) get a full download, clip, then delete.
    """
    if dest.exists():
        print(f"skip (exists) {dest.relative_to(ROOT)}")
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR"):
            _clip(f"/vsicurl/{url}", bounds, dest)
    except rasterio.errors.RasterioIOError:
        full = download(url, dest.parent / "_full" / url.rsplit("/", 1)[-1])
        _clip(str(full), bounds, dest)
        full.unlink()


def _clip(src_path: str, bounds: tuple[float, float, float, float], dest: Path) -> None:
    with rasterio.open(src_path) as src:
        window = from_bounds(*bounds, transform=src.transform).round_offsets().round_lengths()
        data = src.read(window=window)
        profile = src.profile | {
            "height": data.shape[1], "width": data.shape[2],
            "transform": src.window_transform(window),
            "driver": "GTiff", "compress": "deflate", "tiled": True,
        }
    with rasterio.open(dest, "w", **profile) as dst:
        dst.write(data)
    print(f"clipped {dest.relative_to(ROOT)} {data.shape[2]}x{data.shape[1]}")


def main() -> None:
    kel = build_kelurahan()
    minx, miny, maxx, maxy = kel.total_bounds
    b = BBOX_BUFFER_DEG
    bounds = (minx - b, miny - b, maxx + b, maxy + b)
    print(f"jakarta bbox: {tuple(round(float(v), 4) for v in bounds)}")

    clip_remote(WP_POP, bounds, RAW / "worldpop" / "pop_2025.tif")
    for age in WP_AGES_U5 + WP_AGES_65P:
        clip_remote(WP_AGE.format(age=age), bounds, RAW / "worldpop" / f"age_t_{age:02d}_2025.tif")
    clip_remote(WORLDCOVER, bounds, RAW / "worldcover" / "worldcover_2021.tif")
    clip_remote(COP_DEM, bounds, RAW / "dem" / "cop_dem_glo30.tif")
    download(PERGUB_SHS_2026, RAW / "costs" / "pergub_dki_17_2025_shs_2026.pdf")


if __name__ == "__main__":
    main()
