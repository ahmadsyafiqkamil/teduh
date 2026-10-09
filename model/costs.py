"""Square metres to rupiah, carrying the provenance of every figure used.

Returning the sources alongside the amount is not decoration. optimize_portfolio puts a
budget figure in front of a city, and the brief validator will reject that number unless a
Fact can cite where it came from. Four prices come from Kepgub DKI 811/2025 and are verified
against the PDF text layer by pipeline/verify_costs.py; the rest are ASUMSI because a sweep
of all 2005 pages found no reflective roof coating and no growing-medium line item at all
(docs/DECISIONS.md). The caller is handed both and must not flatten the difference.

This module deliberately does NOT import model/scenario.py. scenario.py needs
intervention_cost(), so importing back would be a cycle. The intervention type names are
therefore repeated here as literals, and tests/test_costs.py asserts the two sets stay equal.
"""

from teduh_agent.store import config_entry

# WorldPop cell size at Jakarta's latitude, from pipeline/build_grid.py. Matches the
# CELL_AREA_KM2 used by pipeline/aggregate_kelurahan.py.
CELL_AREA_M2 = 92.8 * 92.2

TREE_PLANTING = "tree_planting"

# Intervention type -> the config entries its price is built from, in citation order.
COST_KEYS: dict[str, tuple[tuple[str, str], ...]] = {
    TREE_PLANTING: (
        ("tree_planting", "tree_unit_idr"),
        ("tree_planting", "planting_unit_idr"),
        ("tree_planting", "canopy_m2_per_tree"),
    ),
    "cool_roof": (("cool_roof", "cost_idr_per_m2"),),
    "green_roof": (("green_roof", "cost_idr_per_m2"),),
}


def trees_for_area(area_m2: float, costs_cfg: dict) -> float:
    """How many trees it takes to produce this much new canopy.

    canopy_m2_per_tree is the bridge between a per-tree price and CONCEPT §7.5's canopy
    percentage points. It is kept as a separate ASUMSI rather than folded into the sourced
    price, so it stays obvious which half is official and which is guessed.
    """
    canopy_per_tree, _ = config_entry(costs_cfg, "tree_planting", "canopy_m2_per_tree")
    return area_m2 / float(canopy_per_tree)


def _sources(itype: str, costs_cfg: dict) -> list[str]:
    return [config_entry(costs_cfg, *path)[1] for path in COST_KEYS[itype]]


def intervention_cost(itype: str, area_m2: float, costs_cfg: dict) -> tuple[float, list[str]]:
    """Capital cost in IDR for treating `area_m2`, plus the source of every figure used."""
    if itype not in COST_KEYS:
        raise ValueError(f"jenis intervensi tidak punya harga: {itype!r}")
    if area_m2 < 0:
        raise ValueError(f"luas tidak boleh negatif: {area_m2}")

    if itype == TREE_PLANTING:
        tree_unit, _ = config_entry(costs_cfg, "tree_planting", "tree_unit_idr")
        planting_unit, _ = config_entry(costs_cfg, "tree_planting", "planting_unit_idr")
        amount = trees_for_area(area_m2, costs_cfg) * (float(tree_unit) + float(planting_unit))
    else:
        per_m2, _ = config_entry(costs_cfg, itype, "cost_idr_per_m2")
        amount = area_m2 * float(per_m2)

    return amount, _sources(itype, costs_cfg)
