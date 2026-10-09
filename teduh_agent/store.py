"""One process-wide load of every artifact the runtime needs (CONCEPT §6.2 principle 3).

Earth Engine is never touched at request time; the app reads what pipeline/ already wrote.
Cloud Run pays one cold load of roughly 9 MB and then answers from memory, which is what
keeps p50 chat latency under the 8 s target. lru_cache makes that a singleton.

Model artifacts are optional by design. api/ and teduh_agent/tools/ must import cleanly
before model/train.py has ever been run, so booster, shap_by_kel and model_card stay None
until those files exist -- callers check and degrade rather than crash at import time.

Artifacts are baked into the container image rather than fetched from GCS at startup; see
docs/DECISIONS.md. TEDUH_DATA_DIR overrides the root for tests and for an image that mounts
data elsewhere.
"""

import json
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import lightgbm as lgb
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]

# Mean LST over good cells on the 2026-10-09 grid. Used only when the grid is absent, so a
# profile request can still state the city baseline instead of returning NaN.
CITY_LST_FALLBACK = 41.8376

GOOD_QUALITY = "good"


@dataclass(frozen=True)
class Store:
    """Every artifact the runtime reads, loaded once.

    kelurahan: one row per kelurahan, indexed by kel_id (264 on real data).
    grid: one row per 100 m cell, indexed by cell_id (75_636 on real data).
    """

    kelurahan: pd.DataFrame
    grid: pd.DataFrame
    boundaries: dict
    scenario_cfg: dict
    costs_cfg: dict
    hvi_cfg: dict
    evidence: list[dict]
    city_lst_mean: float
    booster: Any | None = None
    shap_by_kel: pd.DataFrame | None = None
    model_card: dict | None = None


def _data_root(override: Path | None = None) -> Path:
    if override is not None:
        return Path(override).resolve()
    env = os.environ.get("TEDUH_DATA_DIR")
    return Path(env).resolve() if env else ROOT


def _read_yaml(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"config wajib {path} tidak ada")
    return yaml.safe_load(path.read_text())


def good_cells(grid: pd.DataFrame) -> pd.DataFrame:
    """Cells with enough clean observations to trust thermally (DECISIONS 2026-10-09).

    Low-quality cells stay on the map and keep their residents, but they are excluded from
    every thermal statistic and from model training.
    """
    return grid[grid["lst_quality"] == GOOD_QUALITY]


def config_entry(cfg: dict, *path: str) -> tuple[Any, str]:
    """Read one config constant as (value, source).

    Enforces CLAUDE.md rule 4 at read time: an entry without a `source` raises instead of
    quietly becoming an unattributed number in a policy brief.
    """
    node: Any = cfg
    for key in path:
        if not isinstance(node, dict) or key not in node:
            raise KeyError(f"config path {'.'.join(path)} tidak ada")
        node = node[key]
    if not isinstance(node, dict) or "value" not in node:
        raise KeyError(f"config entry {'.'.join(path)} tidak punya value")
    if "source" not in node:
        raise KeyError(f"config entry {'.'.join(path)} tidak punya source (CLAUDE.md aturan 4)")
    return node["value"], node["source"]


def _load_booster(path: Path) -> Any | None:
    return lgb.Booster(model_file=str(path)) if path.exists() else None


def _load_parquet(path: Path, index: str) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(
            f"artefak {path} tidak ada. Jalankan pipeline dulu: "
            "uv run python -m pipeline.build_grid && "
            "uv run python -m pipeline.aggregate_kelurahan"
        )
    return pd.read_parquet(path).set_index(index)


def load(
    *,
    data_root: Path | None = None,
    kelurahan_path: Path | None = None,
    grid_path: Path | None = None,
) -> Store:
    """Load every artifact. Explicit paths let tests swap in the small fixtures."""
    root = _data_root(data_root)
    processed = root / "data" / "processed"
    model_dir = root / "data" / "model"

    kelurahan = _load_parquet(kelurahan_path or processed / "kelurahan_metrics.parquet", "kel_id")
    grid = _load_parquet(grid_path or processed / "grid_features.parquet", "cell_id")

    boundaries = json.loads((root / "data" / "boundaries" / "kelurahan.geojson").read_text())
    evidence_doc = json.loads((root / "data" / "evidence" / "interventions.json").read_text())

    city_mean = good_cells(grid)["lst_c"].mean()
    shap_path = model_dir / "shap_by_kel.parquet"
    card_path = model_dir / "model_card.json"

    return Store(
        kelurahan=kelurahan,
        grid=grid,
        boundaries=boundaries,
        scenario_cfg=_read_yaml(root / "config" / "scenario.yaml"),
        costs_cfg=_read_yaml(root / "config" / "costs.yaml"),
        hvi_cfg=_read_yaml(root / "config" / "hvi.yaml"),
        evidence=evidence_doc["evidence"],
        city_lst_mean=float(city_mean) if pd.notna(city_mean) else CITY_LST_FALLBACK,
        booster=_load_booster(model_dir / "model.txt"),
        shap_by_kel=pd.read_parquet(shap_path) if shap_path.exists() else None,
        model_card=json.loads(card_path.read_text()) if card_path.exists() else None,
    )


@lru_cache(maxsize=1)
def get_store() -> Store:
    """Process-wide singleton. Call this from tools and routes, never load() directly."""
    return load()
