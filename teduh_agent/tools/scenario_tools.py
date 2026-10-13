"""Agent-facing wrapper over model/scenario.py.

Two responsibilities the engine itself does not have. First, accepting the loose JSON shape
ADK hands over: an intervention may arrive as a named level or as explicit params, and
neither form may be trusted without validation. Second, attaching the literature comparison
CONCEPT §7.5 requires -- a model number presented with no published range beside it is
precisely the overclaiming this product exists to avoid.

The training frame and its quantiles are cached because every scenario call needs them and
re-reading 75_636 rows per request would blow the latency target.
"""

from functools import lru_cache

import pandas as pd
from google.adk.tools import ToolContext

from model.scenario import (
    INTERVENTION_TYPES,
    LEVELS,
    PARAM_NAME,
    Intervention,
    from_level,
    simulate,
    training_quantiles,
)
from model.train import prepare
from teduh_agent.facts import SOURCE_MODEL, fact, record, source_assumption
from teduh_agent.store import config_entry, get_store
from teduh_agent.tools.evidence import evidence_for

INDICATIVE_NOTE = (
    "Angka ini perkiraan model untuk suhu PERMUKAAN (LST), bukan suhu udara, dan "
    "bersifat indikatif untuk penyaringan awal. Bandingkan dengan rentang literatur."
)


@lru_cache(maxsize=1)
def training_frame() -> pd.DataFrame:
    """Model-ready grid, cached for the process."""
    return prepare(get_store().grid.reset_index())


@lru_cache(maxsize=1)
def quantiles() -> pd.Series:
    """Upper bound of the training envelope, for the extrapolation flag.

    The percentile comes from config/scenario.yaml (extrapolation.feature_percentile_max,
    CONCEPT §7.5), not a hard-coded number -- editing the YAML must actually change the
    guard, or CLAUDE.md rule 4 is violated silently.
    """
    percentile, _ = config_entry(
        get_store().scenario_cfg, "extrapolation", "feature_percentile_max"
    )
    return training_quantiles(training_frame(), percentile=percentile)


def _parse(raw: dict) -> Intervention:
    itype = raw.get("type")
    if itype not in INTERVENTION_TYPES:
        raise ValueError(
            f"jenis intervensi {itype!r} tidak dikenal; pilihan: {', '.join(INTERVENTION_TYPES)}"
        )
    if "level" in raw and raw["level"] is not None:
        level = raw["level"]
        if level not in LEVELS[itype]:
            raise ValueError(
                f"level {level!r} tidak dikenal untuk {itype}; pilihan: rendah/sedang/tinggi "
                f"({', '.join(LEVELS[itype])})"
            )
        return from_level(itype, level)

    params = raw.get("params") or {}
    key = PARAM_NAME[itype]
    if key not in params:
        raise ValueError(f"intervensi {itype} butuh level atau params[{key!r}]")
    return Intervention(itype, {key: float(params[key])})


def _facts_for(result, cost_sources: tuple[str, ...]) -> list:
    prefix = f"sim.{result.kel_id}"
    price_source = (
        cost_sources[0] if cost_sources else source_assumption("costs.unknown")
    )
    return [
        fact(f"{prefix}.delta_lst", "Perkiraan perubahan suhu permukaan",
             result.delta_lst_c, "degC", SOURCE_MODEL),
        fact(f"{prefix}.delta_lst_pop", "Perubahan suhu permukaan tertimbang penduduk",
             result.delta_lst_pop_weighted_c, "degC", SOURCE_MODEL),
        fact(f"{prefix}.vulnerable_benefiting", "Warga rentan yang merasakan pendinginan",
             result.vulnerable_benefiting, "jiwa", SOURCE_MODEL),
        fact(f"{prefix}.area", "Luas area intervensi", result.area_m2, "m2", SOURCE_MODEL),
        fact(f"{prefix}.cost", "Perkiraan biaya intervensi", result.cost_idr, "IDR",
             price_source),
    ]


def simulate_intervention(
    kel_ids: list[str],
    interventions: list[dict],
    tool_context: ToolContext | None = None,
) -> dict:
    """Simulasikan dampak intervensi pendinginan pada satu atau beberapa kelurahan.

    Menghitung perkiraan penurunan suhu permukaan, jumlah warga rentan yang merasakannya,
    luas area, dan biayanya. Selalu disertai rentang dari literatur sebagai pembanding.

    Args:
        kel_ids: daftar kode kelurahan, misalnya ["ID3173040002"].
        interventions: daftar intervensi. Setiap item berisi `type`
            ("tree_planting", "cool_roof", atau "green_roof") dan salah satu dari
            `level` ("low", "medium", "high") atau `params`
            ({"canopy_increase_pp": 7.5} untuk pohon, {"adoption_rate": 0.5} untuk atap).

    Returns:
        dict dengan `results` per kelurahan, `evidence` berisi pembanding literatur,
        `note` tentang keterbatasan, dan `facts`.
    """
    if not interventions:
        return {"error": "Belum ada intervensi yang dipilih untuk disimulasikan.", "facts": []}

    store = get_store()
    if store.booster is None:
        return {
            "error": (
                "Model panas belum tersedia, jadi simulasi tidak bisa dijalankan. "
                "Jalankan model.train lebih dulu."
            ),
            "facts": [],
        }

    try:
        parsed = [_parse(raw) for raw in interventions]
    except ValueError as error:
        return {"error": str(error), "facts": []}

    frame = training_frame()
    known = set(frame["kel_id"].unique())
    missing = [kel_id for kel_id in kel_ids if kel_id not in known]
    if missing:
        return {
            "error": f"Kelurahan tidak ada di data TEDUH: {', '.join(missing)}",
            "facts": [],
        }

    results: list[dict] = []
    facts: list = []
    for kel_id in kel_ids:
        cells = frame[frame["kel_id"] == kel_id]
        outcome = simulate(
            cells, parsed, store.booster, store.scenario_cfg, store.costs_cfg, quantiles()
        )
        results.append(
            {
                "kel_id": outcome.kel_id,
                "kel_name": str(store.kelurahan.loc[kel_id, "kel_name"]),
                "delta_lst_c": outcome.delta_lst_c,
                "delta_lst_pop_weighted_c": outcome.delta_lst_pop_weighted_c,
                "vulnerable_benefiting": outcome.vulnerable_benefiting,
                "area_m2": outcome.area_m2,
                "area_by_type": outcome.area_by_type,
                "cost_idr": outcome.cost_idr,
                "extrapolation": outcome.extrapolation,
                "extrapolated_features": list(outcome.extrapolated_features),
                "n_cells": outcome.n_cells,
            }
        )
        facts.extend(_facts_for(outcome, outcome.cost_sources))

    evidence: list[dict] = []
    for intervention in parsed:
        found = evidence_for(intervention.type)
        evidence.extend(found["evidence"])
        facts.extend(found["facts"])

    record(tool_context, facts)
    return {
        "results": results,
        "interventions": [
            {"type": item.type, "params": item.params} for item in parsed
        ],
        "evidence": evidence,
        "note": INDICATIVE_NOTE,
        "map_highlight": list(kel_ids),
        "facts": facts,
    }
