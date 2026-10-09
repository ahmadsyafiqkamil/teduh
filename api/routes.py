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

from functools import lru_cache
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from api.schemas import OptimizeRequest, SimulateRequest, fail, ok
from teduh_agent.store import get_store
from teduh_agent.tools.areas import directory, explain_drivers, get_area_profile
from teduh_agent.tools.optimize import optimize_portfolio
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
