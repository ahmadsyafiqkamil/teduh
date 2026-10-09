"""Budget portfolio selection with OR-Tools CP-SAT (CONCEPT §7.6).

This is the tool that puts a spending plan in front of a city, so two constraints are
hard rather than advisory: total cost must not exceed the budget, and at least
`equity_share` of the spend must land in the top HVI quintile. Without the second one the
optimiser does exactly what a cost-per-degree objective asks and spends the money where
land is cheap and empty, which is the opposite of the product's purpose.

Costs are scaled to millions of rupiah because CP-SAT is integer-only and a Rp 2 billion
budget in whole rupiah produces coefficients large enough to slow the solver badly. Each
package's cost is rounded UP, so the budget constraint stays conservative: the plan can come
in under budget by up to Rp 1 million per package, never over.

Candidate generation runs the scenario engine once per (kelurahan x intervention x level),
which is why MAX_CANDIDATE_AREAS exists -- all 264 kelurahan would be 2_376 simulations and
would blow the latency target.
"""

import math
from dataclasses import dataclass

from google.adk.tools import ToolContext
from ortools.sat.python import cp_model

from model.scenario import INTERVENTION_TYPES, LEVELS, from_level, simulate
from teduh_agent.facts import SOURCE_MODEL, fact, record
from teduh_agent.store import config_entry, get_store
from teduh_agent.tools.areas import directory
from teduh_agent.tools.scenario_tools import quantiles, training_frame

# Weight on general population relative to a vulnerable resident. Deliberately well below 1:
# equity is the product's purpose, so a toddler or an elderly resident must count for more.
LAMBDA_GENERAL_POP = 0.1

# "Top HVI quintile" (CONCEPT §7.6).
TOP_QUINTILE = 0.2

# CP-SAT is integer-only; work in millions of rupiah.
IDR_SCALE = 1_000_000

SOLVER_TIME_LIMIT_S = 20.0

# Each area costs 9 scenario simulations, so the candidate set is capped by HVI rank.
MAX_CANDIDATE_AREAS = 40

# Objective is scaled to an integer too; value is in person-degrees.
VALUE_SCALE = 100


@dataclass(frozen=True)
class Candidate:
    """One (kelurahan, intervention, level) package the solver may buy."""

    kel_id: str
    intervention_type: str
    level: str
    value: float
    cost_idr: float
    delta_lst_c: float
    vulnerable_benefiting: float
    area_m2: float
    in_top_quintile: bool


def _top_quintile_ids() -> set[str]:
    kelurahan = get_store().kelurahan
    cutoff = max(1, int(round(len(kelurahan) * TOP_QUINTILE)))
    return set(kelurahan.nsmallest(cutoff, "hvi_rank").index)


def build_candidates(kel_ids: list[str], allowed: list[str] | None = None) -> list[Candidate]:
    """Simulate every intervention and level for each area, as solver input."""
    store = get_store()
    frame = training_frame()
    q99 = quantiles()
    equitable = _top_quintile_ids()
    types = [t for t in INTERVENTION_TYPES if allowed is None or t in allowed]

    candidates: list[Candidate] = []
    for kel_id in kel_ids:
        cells = frame[frame["kel_id"] == kel_id]
        if cells.empty:
            continue
        vulnerable = float((cells["pop_u5"].fillna(0) + cells["pop_65p"].fillna(0)).sum())
        general = float(cells["pop"].fillna(0).sum())
        people = vulnerable + LAMBDA_GENERAL_POP * general

        for itype in types:
            for level in LEVELS[itype]:
                outcome = simulate(
                    cells,
                    [from_level(itype, level)],
                    store.booster,
                    store.scenario_cfg,
                    store.costs_cfg,
                    q99,
                )
                candidates.append(
                    Candidate(
                        kel_id=kel_id,
                        intervention_type=itype,
                        level=level,
                        value=people * max(0.0, -outcome.delta_lst_c),
                        cost_idr=outcome.cost_idr,
                        delta_lst_c=outcome.delta_lst_c,
                        vulnerable_benefiting=outcome.vulnerable_benefiting,
                        area_m2=outcome.area_m2,
                        in_top_quintile=kel_id in equitable,
                    )
                )
    return candidates


def solve(
    candidates: list[Candidate], budget_idr: int, equity_share: float
) -> tuple[list[Candidate], str]:
    """Multiple-choice knapsack: maximise value within budget and equity constraints."""
    affordable = [c for c in candidates if c.cost_idr > 0 and c.cost_idr <= budget_idr]
    if not affordable or budget_idr <= 0:
        return [], "NO_AFFORDABLE_CANDIDATE"

    model = cp_model.CpModel()
    picked = [model.NewBoolVar(f"pick_{i}") for i in range(len(affordable))]

    # Round each cost UP so the plan can only come in under budget, never over.
    costs = [math.ceil(c.cost_idr / IDR_SCALE) for c in affordable]
    budget_scaled = budget_idr // IDR_SCALE

    model.Add(sum(cost * var for cost, var in zip(costs, picked, strict=True)) <= budget_scaled)

    # At most one level per (kelurahan, intervention).
    groups: dict[tuple[str, str], list] = {}
    for index, candidate in enumerate(affordable):
        groups.setdefault((candidate.kel_id, candidate.intervention_type), []).append(
            picked[index]
        )
    for members in groups.values():
        model.AddAtMostOne(members)

    # Equity: spend in the top HVI quintile must be at least equity_share of total spend.
    # Written as a linear inequality so CP-SAT can handle it directly.
    if equity_share > 0:
        weighted = []
        for index, candidate in enumerate(affordable):
            coefficient = costs[index] * (
                (1.0 - equity_share) if candidate.in_top_quintile else -equity_share
            )
            weighted.append((round(coefficient * 1000), picked[index]))
        model.Add(sum(scaled * var for scaled, var in weighted) >= 0)

    model.Maximize(
        sum(
            round(candidate.value * VALUE_SCALE) * picked[index]
            for index, candidate in enumerate(affordable)
        )
    )

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = SOLVER_TIME_LIMIT_S
    solver.parameters.num_search_workers = 4
    status = solver.Solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return [], solver.StatusName(status)

    chosen = [
        candidate
        for index, candidate in enumerate(affordable)
        if solver.Value(picked[index]) == 1
    ]
    return chosen, solver.StatusName(status)


def _candidate_areas(scope: str) -> list[str]:
    """The highest-HVI areas in scope, capped so candidate generation stays fast."""
    frame = directory()
    if scope and scope.lower() != "all":
        if scope in frame["kota_id"].values:
            frame = frame[frame["kota_id"] == scope]
        elif scope in frame["kec_id"].values:
            frame = frame[frame["kec_id"] == scope]
        elif scope in frame.index:
            frame = frame.loc[[scope]]
        else:
            from teduh_agent.tools.areas import find_area

            located = find_area(scope)
            if not located["matches"]:
                return []
            frame = frame.loc[[m["kel_id"] for m in located["matches"]]]
    return list(frame.nsmallest(min(MAX_CANDIDATE_AREAS, len(frame)), "hvi_rank").index)


def optimize_portfolio(
    scope: str = "all",
    budget_idr: int = 0,
    equity_share: float | None = None,
    allowed: list[str] | None = None,
    tool_context: ToolContext | None = None,
) -> dict:
    """Susun paket intervensi terbaik dalam batas anggaran, dengan kendala keadilan.

    Memilih kombinasi kelurahan dan intervensi yang memaksimalkan pendinginan tertimbang
    jumlah warga rentan per rupiah, dengan jaminan total biaya tidak melewati anggaran dan
    minimal sebagian anggaran masuk ke kelurahan paling rentan.

    Args:
        scope: "all" untuk seluruh DKI, atau nama/kode kota atau kecamatan.
        budget_idr: anggaran total dalam rupiah, misalnya 2000000000 untuk Rp 2 miliar.
        equity_share: porsi minimum anggaran untuk kuintil HVI teratas, 0 sampai 1.
            Kalau kosong, memakai 0,6 dari config.
        allowed: opsional, batasi jenis intervensi, misalnya ["cool_roof"].

    Returns:
        dict dengan `packages`, `total_cost_idr`, `equity_share_achieved`,
        `map_highlight`, dan `facts`.
    """
    if budget_idr <= 0:
        return {"error": "Anggaran harus lebih besar dari nol.", "facts": []}

    store = get_store()
    if store.booster is None:
        return {
            "error": "Model panas belum tersedia. Jalankan model.train lebih dulu.",
            "facts": [],
        }

    configured, _ = config_entry(store.costs_cfg, "optimizer", "equity_share_min")
    requested = float(configured) if equity_share is None else float(equity_share)
    if not 0.0 <= requested <= 1.0:
        return {"error": "Porsi keadilan harus antara 0 dan 1.", "facts": []}

    if allowed is not None:
        unknown = [t for t in allowed if t not in INTERVENTION_TYPES]
        if unknown:
            return {"error": f"Jenis intervensi tidak dikenal: {', '.join(unknown)}", "facts": []}

    areas = _candidate_areas(scope)
    if not areas:
        return {"error": f"Wilayah {scope!r} tidak ada di data TEDUH.", "facts": []}

    candidates = build_candidates(areas, allowed)
    chosen, status = solve(candidates, int(budget_idr), requested)

    if not chosen:
        return {
            "error": (
                f"Tidak ada paket yang bisa dipilih dengan anggaran Rp {budget_idr:,} dan "
                f"porsi keadilan {requested:.0%} (status solver: {status}). "
                "Coba naikkan anggaran atau turunkan porsi keadilan."
            ),
            "packages": [],
            "facts": [],
        }

    total_cost = sum(c.cost_idr for c in chosen)
    equitable_cost = sum(c.cost_idr for c in chosen if c.in_top_quintile)
    achieved = equitable_cost / total_cost if total_cost else 0.0
    names = directory()["kel_name"]

    packages = [
        {
            "kel_id": c.kel_id,
            "kel_name": names.get(c.kel_id, c.kel_id),
            "intervention_type": c.intervention_type,
            "level": c.level,
            "cost_idr": c.cost_idr,
            "delta_lst_c": c.delta_lst_c,
            "vulnerable_benefiting": c.vulnerable_benefiting,
            "area_m2": c.area_m2,
            "in_top_hvi_quintile": c.in_top_quintile,
        }
        for c in sorted(chosen, key=lambda c: -c.value)
    ]

    facts = [
        fact("opt.budget", "Anggaran yang tersedia", float(budget_idr), "IDR", SOURCE_MODEL),
        fact("opt.total_cost", "Total biaya portofolio", total_cost, "IDR", SOURCE_MODEL),
        fact("opt.n_packages", "Jumlah paket terpilih", len(chosen), "paket", SOURCE_MODEL),
        fact("opt.equity_share", "Porsi anggaran untuk kuintil HVI teratas", achieved, "fraksi",
             SOURCE_MODEL),
        fact("opt.total_cooling", "Total pendinginan tertimbang penduduk",
             sum(c.value for c in chosen), "jiwa-derajat", SOURCE_MODEL),
        fact("opt.vulnerable_reached", "Warga rentan yang merasakan pendinginan",
             sum(c.vulnerable_benefiting for c in chosen), "jiwa", SOURCE_MODEL),
    ]
    record(tool_context, facts)

    return {
        "packages": packages,
        "total_cost_idr": total_cost,
        "budget_idr": float(budget_idr),
        "equity_share_requested": requested,
        "equity_share_achieved": achieved,
        "solver_status": status,
        "n_candidates": len(candidates),
        "note": (
            "Perkiraan biaya memakai harga satuan dari config/costs.yaml. "
            "Pendinginan adalah suhu permukaan dan bersifat indikatif."
        ),
        "map_highlight": [p["kel_id"] for p in packages],
        "facts": facts,
    }
