"""REST endpoints for the map, the drawer, the sliders, and the budget form.

Every handler delegates to the same tool function the agent calls, passing
tool_context=None. That is deliberate and worth protecting: if the slider path ever grew
its own copy of the scenario maths, the UI and the agent could disagree about the same
kelurahan, and a planner would have no way to tell which number to trust.

The map payload is built once and cached. Coordinates are rounded to five decimals (~1 m)
because kelurahan boundaries arrive at centimetre precision, which is 2.2 MB of pointless
bytes for a choropleth. Rounding needs no geometry library, which matters because geopandas
lives in the pipeline dependency group and is not installed in the runtime image.
"""

import io
import re
from functools import lru_cache
from typing import Annotated, Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse

from api.schemas import OptimizeRequest, SimulateRequest, fail, ok
from teduh_agent.store import get_store
from teduh_agent.tools.areas import directory, explain_drivers, get_area_profile
from teduh_agent.tools.brief import BRIEF_DIR
from teduh_agent.tools.optimize import optimize_portfolio
from teduh_agent.tools.roof import analyze_roof_bytes, recommend_roof_action
from teduh_agent.tools.scenario_tools import simulate_intervention

router = APIRouter(prefix="/api")

# ~10 m at Jakarta's latitude. Still finer than the 0.9 px map line width, and it keeps the
# payload well under the 1.5 MB budget the frontend pays per cold load.
COORD_PRECISION = 4

# Metrics the four map layers and the hover tooltip read straight off GeoJSON properties.
MAP_METRICS: tuple[str, ...] = (
    "lst_c_mean",
    "lst_anomaly_c",
    "hvi",
    "hvi_rank",
    "H",
    "E",
    "S",
    "A",
    "ndvi_mean",
    "tree_frac_mean",
    "built_frac_mean",
    "pop",
    "pop_density",
    "exposed_vulnerable",
)

NAME_PROPERTIES = ("kel_id", "kel_name", "kec_id", "kec_name", "kota_id", "kota_name")

# brief_id reaches the filesystem, so it is matched against a strict pattern rather than
# sanitised. uuid4().hex[:12] is always 12 lowercase hex characters.
BRIEF_ID_PATTERN = r"^[0-9a-f]{12}$"

# Phone photos routinely land under this; anything larger is abuse or a mistake.
MAX_PHOTO_BYTES = 8 * 1024 * 1024

ALLOWED_PHOTO_TYPES = {"image/jpeg", "image/png"}

# Matches pipeline/strip_exif.py so the offline test set and the live path agree.
MAX_PHOTO_EDGE_PX = 2048

JPEG_QUALITY = 90

# A kelurahan name, nothing finer. Street, number, RT and RW are rejected outright.
# Word boundaries, not substrings: "Rawa Buaya" and "Grogol" are real kelurahan names and
# a careless `"rw" in name` check would reject them.
ADDRESS_PATTERN = re.compile(r"\b(?:jl|jalan|no|rt|rw|gang|gg|blok)\b", re.IGNORECASE)
MAX_KELURAHAN_NAME_LEN = 60


def _round_coords(node: Any) -> Any:
    """Recursively round coordinate numbers, leaving the nesting structure untouched."""
    if isinstance(node, list):
        return [_round_coords(item) for item in node]
    if isinstance(node, float):
        return round(node, COORD_PRECISION)
    return node


def _clean(value: Any) -> Any:
    """JSON cannot carry NaN. A missing metric must be null, not the string 'NaN'."""
    if value is None:
        return None
    try:
        import math

        number = float(value)
        return None if math.isnan(number) else number
    except (TypeError, ValueError):
        return value


@lru_cache(maxsize=1)
def map_payload() -> dict:
    """GeoJSON plus per-kelurahan metrics, built once per process."""
    store = get_store()
    frame = directory()

    features = []
    for feature in store.boundaries["features"]:
        kel_id = feature["properties"]["kel_id"]
        properties = {key: feature["properties"].get(key) for key in NAME_PROPERTIES}
        if kel_id in frame.index:
            row = frame.loc[kel_id]
            properties.update({metric: _clean(row.get(metric)) for metric in MAP_METRICS})
        else:
            properties.update({metric: None for metric in MAP_METRICS})

        features.append(
            {
                "type": "Feature",
                "properties": properties,
                "geometry": {
                    "type": feature["geometry"]["type"],
                    "coordinates": _round_coords(feature["geometry"]["coordinates"]),
                },
            }
        )

    return {
        "type": "FeatureCollection",
        "features": features,
        "attribution": (
            "Batas: HDX COD-AB Indonesia (CC BY-IGO) · LST: USGS Landsat 8/9 · "
            "Vegetasi: ESA WorldCover v200 · Penduduk: WorldPop 2025 · "
            "Bangunan: Google Open Buildings Temporal v1 · Elevasi: Copernicus DEM"
        ),
    }


@router.get("/health")
def health() -> dict:
    """Readiness plus what is actually loaded, so a broken deploy is visible immediately."""
    store = get_store()
    return ok(
        {
            "n_kelurahan": len(store.kelurahan),
            "n_cells": len(store.grid),
            "city_lst_mean": store.city_lst_mean,
            "model_loaded": store.booster is not None,
            "shap_loaded": store.shap_by_kel is not None,
        }
    )


@router.get("/kelurahan")
def list_kelurahan() -> dict:
    """GeoJSON with metrics for the choropleth."""
    return ok(map_payload())


@router.get("/kelurahan/{kel_id}")
def kelurahan_detail(kel_id: str) -> Any:
    """Full profile plus SHAP drivers, which is everything the drawer renders."""
    profile = get_area_profile(kel_id)
    if "error" in profile:
        return JSONResponse(status_code=404, content=fail(profile["error"]))

    drivers = explain_drivers(kel_id)
    payload = dict(profile)
    payload["drivers"] = drivers.get("drivers", [])
    payload["drivers_unavailable"] = drivers.get("error")
    payload["facts"] = profile["facts"] + drivers.get("facts", [])
    return ok(payload)


@router.post("/simulate")
def simulate(request: SimulateRequest) -> Any:
    """Scenario straight from the sliders. No LLM in this path."""
    result = simulate_intervention(
        request.kel_ids,
        [item.model_dump(exclude_none=True) for item in request.interventions],
    )
    if "error" in result:
        return JSONResponse(status_code=400, content=fail(result["error"]))
    return ok(result)


@router.post("/optimize")
def optimize(request: OptimizeRequest) -> Any:
    """Portfolio straight from the budget form. No LLM in this path."""
    result = optimize_portfolio(
        scope=request.scope,
        kel_ids=request.kel_ids,
        budget_idr=request.budget_idr,
        equity_share=request.equity_share,
        allowed=request.allowed,
    )
    if "error" in result:
        return JSONResponse(status_code=400, content=fail(result["error"]))
    return ok(result)


@router.get("/model-card")
def model_card() -> Any:
    """Metrics and limitations for the "Tentang & Sumber Data" page."""
    store = get_store()
    if store.model_card is None:
        raise HTTPException(
            status_code=404,
            detail="Model card belum tersedia. Model belum dilatih.",
        )
    return ok(store.model_card)


@router.get("/brief/{brief_id}")
def brief(brief_id: str, format: str = "md") -> Any:
    """Serve a rendered brief as Markdown or PDF."""
    if not re.match(BRIEF_ID_PATTERN, brief_id):
        return JSONResponse(status_code=404, content=fail("Brief tidak ditemukan."))
    if format not in {"md", "pdf"}:
        return JSONResponse(
            status_code=422, content=fail("Format harus 'md' atau 'pdf'.")
        )

    path = BRIEF_DIR / f"{brief_id}.{format}"
    if not path.exists():
        return JSONResponse(
            status_code=404,
            content=fail(
                "Brief tidak ditemukan. Tautan brief hanya berlaku selama instance "
                "yang membuatnya masih hidup."
            ),
        )

    if format == "pdf":
        return FileResponse(
            path,
            media_type="application/pdf",
            filename=f"teduh-brief-{brief_id}.pdf",
        )
    return PlainTextResponse(path.read_text(encoding="utf-8"), media_type="text/markdown")


def strip_metadata(data: bytes) -> tuple[bytes, str]:
    """Re-encode the pixels into a fresh container, discarding all metadata.

    This decodes and re-saves rather than deleting tags, because a geotagged roof photo is
    a home address (CLAUDE.md rule 8) and tag deletion can miss a container -- XMP, IPTC, a
    thumbnail carrying its own EXIF. Rebuilding the file means there is nothing to miss.
    Mirrors pipeline/strip_exif.py so the offline test set and the live path agree.
    """
    from PIL import Image, ImageOps

    try:
        image = Image.open(io.BytesIO(data))
        image.load()
    except Exception as error:  # noqa: BLE001 -- Pillow raises many unrelated types
        raise ValueError(f"berkas bukan gambar yang bisa dibaca: {error}") from error

    # Honour the orientation tag before dropping it, or portrait photos come out sideways
    # and the model reads a wall as a roof.
    image = ImageOps.exif_transpose(image).convert("RGB")
    image.thumbnail((MAX_PHOTO_EDGE_PX, MAX_PHOTO_EDGE_PX))

    # Raw pixels into a brand-new image. `convert()` and `copy()` both carry `.info` across,
    # and anything left in info["exif"] gets re-emitted on save -- which would defeat the
    # whole point. frombytes() starts with an empty info dict.
    clean = Image.frombytes("RGB", image.size, image.tobytes())

    buffer = io.BytesIO()
    clean.save(buffer, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    return buffer.getvalue(), "image/jpeg"


def _looks_like_an_address(value: str) -> bool:
    return len(value) > MAX_KELURAHAN_NAME_LEN or ADDRESS_PATTERN.search(value) is not None


@router.post("/roof")
async def roof(
    photo: Annotated[UploadFile, File()],
    kelurahan: Annotated[str | None, Form()] = None,
) -> Any:
    """Classify an uploaded roof photo and return a rule-based recommendation.

    The photo is stripped of metadata in memory and never written to disk: the demo has no
    need to keep it, and not storing it is a stronger privacy guarantee than a lifecycle
    rule (docs/DECISIONS.md).

    Guard order is load-bearing. Content type, size and location are all checked before the
    pixels are decoded or sent anywhere, so a rejected upload costs no Gemini call.
    """
    if photo.content_type not in ALLOWED_PHOTO_TYPES:
        return JSONResponse(
            status_code=415,
            content=fail(
                "Format foto harus image/jpeg atau image/png, "
                f"bukan {photo.content_type!r}."
            ),
        )

    raw = await photo.read()
    if len(raw) > MAX_PHOTO_BYTES:
        return JSONResponse(
            status_code=413,
            content=fail(
                f"Foto terlalu besar, maksimal {MAX_PHOTO_BYTES // (1024 * 1024)} MB."
            ),
        )

    if kelurahan and _looks_like_an_address(kelurahan):
        return JSONResponse(
            status_code=422,
            content=fail(
                "Lokasi hanya boleh sampai tingkat kelurahan. Jangan menuliskan nama "
                "jalan, nomor rumah, RT, atau RW."
            ),
        )

    try:
        cleaned, mime_type = strip_metadata(raw)
    except ValueError as error:
        return JSONResponse(status_code=400, content=fail(str(error)))

    try:
        analysed = analyze_roof_bytes(cleaned, mime_type)
    except Exception:  # noqa: BLE001 -- any genai/network failure
        return JSONResponse(
            status_code=502,
            content=fail("Analisis foto sedang tidak tersedia. Coba lagi sebentar lagi."),
        )

    advice = recommend_roof_action(analysed)
    if "error" in advice:
        return JSONResponse(status_code=400, content=fail(advice["error"]))

    return ok(
        {
            "roof": analysed,
            "recommendation": advice["recommendation"],
            "evidence": advice["evidence"],
            "guidance": advice["guidance"],
            "kelurahan": kelurahan or None,
            "facts": advice["facts"],
        }
    )
