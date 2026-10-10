"""Translate an intervention into feature changes, then ask the model for a new LST.

CONCEPT §7.5. The engine never invents a constant: every number comes through
store.config_entry(), which refuses an entry that has no source.

The physics DIRECTION is guaranteed upstream by the monotonic constraints in
model/train.py, not by anything here. This module's job is to keep the feature deltas
honest, which means respecting three caps that are easy to forget:

  - canopy cannot be planted on buildings or open water, nor on ground that already carries
    canopy, so the gain is capped by the cell's remaining plantable headroom;
  - cool roof only repaints roof area that exists, so the treated fraction scales with
    roof_frac;
  - green roof only applies to the flat share of that roof area, and must not be charged for
    roof the cool-roof intervention already took.

Skipping those caps is how a scenario tool starts promising 10 pp of new canopy in a cell
that is 100 % built, and then billing a city for it.

treated_fractions() is the single source of truth for "how much of this cell is touched".
apply_interventions() and intervened_area_m2() both read from it, which is what guarantees
the area billed equals the area simulated.
"""

from dataclasses import dataclass

import lightgbm as lgb
import numpy as np
import pandas as pd

from model.config import config_entry
from model.costs import CELL_AREA_M2, intervention_cost
from model.train import FEATURES, predict

TREE = "tree_planting"
COOL_ROOF = "cool_roof"
GREEN_ROOF = "green_roof"

INTERVENTION_TYPES: tuple[str, str, str] = (TREE, COOL_ROOF, GREEN_ROOF)

PARAM_NAME: dict[str, str] = {
    TREE: "canopy_increase_pp",
    COOL_ROOF: "adoption_rate",
    GREEN_ROOF: "adoption_rate",
}

# Levels the optimiser enumerates and the UI sliders snap to (CONCEPT §7.6).
# tree_planting is in percentage points of cell area; the roof measures are adoption rates.
LEVELS: dict[str, dict[str, float]] = {
    TREE: {"low": 2.0, "medium": 5.0, "high": 10.0},
    COOL_ROOF: {"low": 0.25, "medium": 0.50, "high": 0.75},
    GREEN_ROOF: {"low": 0.10, "medium": 0.20, "high": 0.35},
}

PERCENTAGE_POINTS = 100.0

# Features clipped back into their physical range after the deltas land.
BOUNDED_FEATURES = ("tree_frac", "built_frac", "water_frac", "roof_frac", "albedo", "ndvi")

# Land-cover fractions are bounded to [0,1] by definition, and the training grid already
# covers that whole range (max = 1,0 for all four). q99 is not a meaningful envelope here:
# a cell planted to the brim sits inside the training data, not beyond it.
FRACTION_FEATURES = ("tree_frac", "built_frac", "water_frac", "roof_frac")


@dataclass(frozen=True)
class Intervention:
    """One intervention at one intensity. The params key is given by PARAM_NAME."""

    type: str
    params: dict


@dataclass(frozen=True)
class ScenarioResult:
    """What one kelurahan gets from one set of interventions.

    delta_lst_c is negative when the scenario cools, which is the desirable direction.
    """

    kel_id: str
    delta_lst_c: float
    delta_lst_pop_weighted_c: float
    vulnerable_benefiting: float
    area_m2: float
    area_by_type: dict[str, float]
    cost_idr: float
    cost_sources: tuple[str, ...]
    extrapolation: bool
    extrapolated_features: tuple[str, ...]
    n_cells: int


def from_level(itype: str, level: str) -> Intervention:
    """Build an Intervention from a named intensity."""
    if itype not in INTERVENTION_TYPES:
        raise ValueError(f"jenis intervensi tidak dikenal: {itype!r}")
    if level not in LEVELS[itype]:
        raise ValueError(f"level tidak dikenal untuk {itype}: {level!r}")
    return Intervention(itype, {PARAM_NAME[itype]: LEVELS[itype][level]})


def plantable_headroom(cells: pd.DataFrame) -> pd.Series:
    """Fraction of each cell that could still take new canopy.

    Buildings and water are unplantable, and ground already under canopy cannot be planted
    twice. Clipped at zero because the three fractions are measured independently and can
    sum slightly past 1.
    """
    headroom = 1.0 - cells["built_frac"] - cells["water_frac"] - cells["tree_frac"]
    return headroom.clip(lower=0.0, upper=1.0)


def _by_type(interventions: list[Intervention]) -> dict[str, Intervention]:
    chosen: dict[str, Intervention] = {}
    for intervention in interventions:
        if intervention.type not in INTERVENTION_TYPES:
            raise ValueError(f"jenis intervensi tidak dikenal: {intervention.type!r}")
        if intervention.type in chosen:
            raise ValueError(f"intervensi ganda untuk jenis yang sama: {intervention.type}")
        chosen[intervention.type] = intervention
    return chosen


def treated_fractions(
    cells: pd.DataFrame, interventions: list[Intervention], scenario_cfg: dict
) -> dict[str, pd.Series]:
    """Fraction of each cell's area actually touched by each intervention.

    Green roof is resolved before cool roof so the two cannot repaint the same square metre:
    cool roof gets whatever roof the green roof did not take.
    """
    chosen = _by_type(interventions)
    fractions: dict[str, pd.Series] = {}
    roof_taken = pd.Series(0.0, index=cells.index)

    if GREEN_ROOF in chosen:
        flat_share, _ = config_entry(scenario_cfg, "green_roof", "flat_roof_share")
        adoption = float(chosen[GREEN_ROOF].params[PARAM_NAME[GREEN_ROOF]])
        green = cells["roof_frac"] * float(flat_share) * adoption
        fractions[GREEN_ROOF] = green
        roof_taken = roof_taken + green

    if COOL_ROOF in chosen:
        adoption = float(chosen[COOL_ROOF].params[PARAM_NAME[COOL_ROOF]])
        available = (cells["roof_frac"] - roof_taken).clip(lower=0.0)
        fractions[COOL_ROOF] = available * adoption

    if TREE in chosen:
        requested = float(chosen[TREE].params[PARAM_NAME[TREE]]) / PERCENTAGE_POINTS
        fractions[TREE] = plantable_headroom(cells).clip(upper=requested)

    return fractions


def apply_interventions(
    cells: pd.DataFrame, interventions: list[Intervention], scenario_cfg: dict
) -> pd.DataFrame:
    """Return a NEW frame with model features moved by the interventions."""
    after = cells.copy()
    fractions = treated_fractions(cells, interventions, scenario_cfg)

    if GREEN_ROOF in fractions:
        ndvi_green, _ = config_entry(scenario_cfg, "green_roof", "ndvi_green")
        albedo_green, _ = config_entry(scenario_cfg, "green_roof", "albedo_green")
        share = fractions[GREEN_ROOF]
        # Only the greened share moves, and greenness only upward: a roof garden cannot make
        # a cell less green than it already was.
        after["ndvi"] = after["ndvi"] + share * (
            float(ndvi_green) - after["ndvi"]
        ).clip(lower=0.0)
        after["albedo"] = after["albedo"] + share * (float(albedo_green) - after["albedo"])

    if COOL_ROOF in fractions:
        albedo_cool, _ = config_entry(scenario_cfg, "cool_roof", "albedo_cool")
        albedo_base, _ = config_entry(scenario_cfg, "cool_roof", "albedo_roof_base")
        after["albedo"] = after["albedo"] + fractions[COOL_ROOF] * (
            float(albedo_cool) - float(albedo_base)
        )

    if TREE in fractions:
        ndvi_tree, _ = config_entry(scenario_cfg, "tree_planting", "ndvi_tree")
        delta = fractions[TREE]
        after["ndvi"] = after["ndvi"] + delta * (float(ndvi_tree) - after["ndvi"]).clip(lower=0.0)
        after["tree_frac"] = after["tree_frac"] + delta

    for column in BOUNDED_FEATURES:
        if column in after.columns:
            after[column] = after[column].clip(lower=0.0, upper=1.0)
    return after


def intervened_area_m2(
    cells: pd.DataFrame, interventions: list[Intervention], scenario_cfg: dict
) -> dict[str, float]:
    """Square metres treated per intervention type, from the same fractions the model saw."""
    fractions = treated_fractions(cells, interventions, scenario_cfg)
    return {itype: float(series.sum() * CELL_AREA_M2) for itype, series in fractions.items()}


def training_quantiles(frame: pd.DataFrame, percentile: float | None = None) -> pd.Series:
    """Upper bound of the training envelope, per feature.

    A scenario that pushes a feature past this is asking the model about a city it has never
    seen, so the result gets flagged rather than quietly reported.
    """
    cut = 99.0 if percentile is None else float(percentile)
    return frame[FEATURES].quantile(cut / 100.0)


def _extrapolated(
    after: pd.DataFrame, before: pd.DataFrame, train_q99: pd.Series
) -> tuple[str, ...]:
    """Features the intervention pushed beyond the training envelope.

    The comparison is per cell, not per feature-frame. Only cells whose value actually moved
    may trip the flag; a cell that already sat above the 99th percentile before any
    intervention is a baseline outlier the model was trained on, not a scenario pushing it
    somewhere new -- flagging it would cry wolf on every modest scenario in a dense
    kelurahan.

    Land-cover fractions are skipped entirely: they saturate at 1,0 inside the training
    range, so q99 is a meaningless envelope for them.
    """
    flagged: list[str] = []
    for name in FEATURES:
        if name not in after.columns or name not in before.columns:
            continue
        if name not in train_q99.index or name in FRACTION_FEATURES:
            continue
        a = after[name].to_numpy(dtype=float)
        b = before[name].to_numpy(dtype=float)
        moved = ~((a == b) | (np.isnan(a) & np.isnan(b)))
        if moved.any() and a[moved].max() > train_q99[name]:
            flagged.append(name)
    return tuple(flagged)


def _population_weighted(delta: np.ndarray, pop: pd.Series) -> float:
    """Mean delta weighted by residents, falling back to the plain mean when nobody lives here.

    1_207 good cells have NaN pop, so a naive weighted mean returns NaN and the UI would
    print "NaN °C" to a planner.
    """
    weights = pop.fillna(0.0).to_numpy()
    if weights.sum() <= 0:
        return float(np.mean(delta))
    return float(np.average(delta, weights=weights))


def simulate(
    cells: pd.DataFrame,
    interventions: list[Intervention],
    booster: lgb.Booster,
    scenario_cfg: dict,
    costs_cfg: dict,
    train_q99: pd.Series,
) -> ScenarioResult:
    """Predict the cooling, the people reached, the area, and the cost for one kelurahan."""
    if cells.empty:
        raise ValueError("tidak ada sel untuk disimulasikan")
    kel_ids = cells["kel_id"].unique()
    if len(kel_ids) != 1:
        raise ValueError(f"simulate() hanya untuk satu kelurahan, dapat {len(kel_ids)}")

    after = apply_interventions(cells, interventions, scenario_cfg)
    delta = predict(booster, after) - predict(booster, cells)

    threshold, _ = config_entry(scenario_cfg, "extrapolation", "min_cooling_for_benefit_c")
    vulnerable = cells["pop_u5"].fillna(0.0) + cells["pop_65p"].fillna(0.0)
    benefiting = float(vulnerable[delta <= float(threshold)].sum())

    areas = intervened_area_m2(cells, interventions, scenario_cfg)
    cost_total = 0.0
    sources: list[str] = []
    for itype, area in areas.items():
        amount, itype_sources = intervention_cost(itype, area, costs_cfg)
        cost_total += amount
        sources.extend(itype_sources)

    flagged = _extrapolated(after, cells, train_q99)

    return ScenarioResult(
        kel_id=str(kel_ids[0]),
        delta_lst_c=float(np.mean(delta)),
        delta_lst_pop_weighted_c=_population_weighted(delta, cells["pop"]),
        vulnerable_benefiting=benefiting,
        area_m2=float(sum(areas.values())),
        area_by_type=areas,
        cost_idr=cost_total,
        cost_sources=tuple(dict.fromkeys(sources)),
        extrapolation=bool(flagged),
        extrapolated_features=flagged,
        n_cells=len(cells),
    )
