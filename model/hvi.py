"""Heat Vulnerability Index: the IPCC hazard x exposure x vulnerability framing (CONCEPT §7.4).

Lifted out of pipeline/aggregate_kelurahan.py because the formula is needed in two places at
once. The pipeline bakes default-weight HVI into kelurahan_metrics.parquet, and
rank_priority_areas(weights=...) recomputes it at request time when a planner reweights the
policy choice from the UI. Two copies of this arithmetic would drift, and a drifting HVI
means the map and the ranking disagree about who is most vulnerable -- the one thing this
product cannot get wrong.

Every component is a within-city percentile, so every figure is relative to Jakarta and must
never be read as an absolute risk. The weights are a policy choice, not a measurement.
"""

import pandas as pd

DEFAULT_WEIGHTS: dict[str, float] = {"wE": 0.4, "wS": 0.3, "wA": 0.3}

WEIGHT_KEYS = ("wE", "wS", "wA")
COMPONENT_COLUMNS = ("H", "E", "S", "A")
REQUIRED_COLUMNS = ("lst_c_mean", "pop_density", "vulnerable_share", "tree_frac_mean")


def percentile(series: pd.Series) -> pd.Series:
    """Within-city percentile rank in [0, 1]. NaN stays NaN, never a middling 0.5."""
    return series.rank(pct=True, na_option="keep")


def load_weights(hvi_cfg: dict) -> dict[str, float]:
    """Read the default weights from config/hvi.yaml."""
    weights = {key: float(hvi_cfg["weights"][key]["value"]) for key in WEIGHT_KEYS}
    total = sum(weights.values())
    if abs(total - 1.0) > 1e-9:
        print(f"PERINGATAN: bobot HVI berjumlah {total:.3f}, bukan 1,0")
    return weights


def components(kel: pd.DataFrame) -> pd.DataFrame:
    """Hazard, exposure, sensitivity, and lack of adaptive capacity, each a percentile.

    A is inverted on purpose: it measures the ABSENCE of canopy, so the leafiest kelurahan
    scores lowest.
    """
    missing = [column for column in REQUIRED_COLUMNS if column not in kel.columns]
    if missing:
        raise KeyError(f"kolom wajib untuk HVI tidak ada: {missing}")
    return pd.DataFrame(
        {
            "H": percentile(kel["lst_c_mean"]),
            "E": percentile(kel["pop_density"]),
            "S": percentile(kel["vulnerable_share"]),
            "A": 1.0 - percentile(kel["tree_frac_mean"]),
        },
        index=kel.index,
    )


def hvi(comp: pd.DataFrame, weights: dict[str, float] | None = None) -> pd.Series:
    """HVI = H * (wE*E + wS*S + wA*A), bounded in [0, 1] because every term is.

    Weights arrive from the UI, so they are validated here rather than trusted.
    """
    active = DEFAULT_WEIGHTS if weights is None else weights
    missing = [key for key in WEIGHT_KEYS if key not in active]
    if missing:
        raise KeyError(f"bobot HVI tidak lengkap, kurang: {missing}")
    negative = [key for key in WEIGHT_KEYS if active[key] < 0]
    if negative:
        raise ValueError(f"bobot HVI tidak boleh negatif: {negative}")

    weighted = active["wE"] * comp["E"] + active["wS"] * comp["S"] + active["wA"] * comp["A"]
    return (comp["H"] * weighted).rename("hvi")


def rank(hvi_series: pd.Series) -> pd.Series:
    """1 = most vulnerable. method="min" so tied kelurahan share the better rank."""
    return hvi_series.rank(ascending=False, method="min").astype("Int64").rename("hvi_rank")
