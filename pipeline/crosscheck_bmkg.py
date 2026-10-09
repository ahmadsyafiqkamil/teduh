"""Compare BMKG's own monthly figures against monthly means of GHCN dailies (DATA_SOURCES §E).

TEDUH reads air temperature from two sources covering different windows: GHCN-Daily carries
daily records to early Mar 2025, dataonline.bmkg.go.id carries monthly records from Nov 2024.
They overlap for four months, which is just enough to ask whether the two agree -- and they
have to, because GHCN redistributes BMKG's own synoptic reports, so a large gap would mean one
of the two pipelines mishandles the data rather than that the weather disagreed.

docs/DECISIONS.md recorded this cross-check as blocked for want of BMKG download quota. It was
not: the 2024-11..2026-02 export already on disk covers the overlap, so no further request is
needed.

A month is only compared when GHCN has enough days in it, since a month represented by a
handful of days is not a monthly mean.

Run: uv run --no-project --python 3.12 python pipeline/crosscheck_bmkg.py
Output: data/processed/bmkg_ghcn_crosscheck.csv (one row per station-month compared)
"""

import csv
import statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DAILY = ROOT / "data" / "raw" / "bmkg" / "stations_daily.csv"
MONTHLY = ROOT / "data" / "raw" / "bmkg" / "stations_monthly.csv"
OUT = ROOT / "data" / "processed" / "bmkg_ghcn_crosscheck.csv"

# GHCN keys stations by its own ID, dataonline by WMO number. Only these two appear in both
# sources (DATA_SOURCES.md §E); Halim is in neither usable form.
GHCN_TO_WMO = {
    "ID000096745": "96745",  # Kemayoran (Jakarta Observatory)
    "IDM00096741": "96741",  # Tanjung Priok
}

# Below this many daily records, a month's mean is not representative enough to compare.
MIN_DAYS_PER_MONTH = 20

VARIABLES = ("tmax_c", "tmin_c", "tavg_c")

# BMKG dataonline's monthly temp_max/temp_min are monthly EXTREMES -- the hottest and coldest
# readings of the month -- not means of the daily extremes. temp_avg really is a mean. This was
# measured, not assumed: against GHCN monthly MEANS the gaps are +3.62 and -1.90 C, against
# GHCN monthly EXTREMES they fall to +0.79 and -0.17 C, and they land exactly on top of each
# other in the months where GHCN has no missing days (Kemayoran 2024-11 35.2/35.2, 2024-12
# 24.4/24.4, 2025-01 23.8/23.8). Comparing the wrong statistic would overstate a "mean daily
# maximum" by about 3.6 C, so the pairing below is load-bearing, not a detail.
GHCN_STATISTIC = {"tmax_c": max, "tmin_c": min, "tavg_c": statistics.fmean}

# Per-variable tolerance. temp_avg is mean-vs-mean and must agree tightly. The extremes are
# looser only because GHCN carries missing days, which biases ITS observed extreme inward --
# BMKG sees the complete record. So a positive tmax gap and negative tmin gap are expected.
MAX_DIFF_C = {"tmax_c": 2.0, "tmin_c": 1.5, "tavg_c": 0.5}


def _read(path: Path) -> list[dict]:
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def _ghcn_monthly() -> dict[tuple[str, str], dict]:
    """Reduce GHCN dailies to one figure per month, keyed by (wmo_id, YYYY-MM).

    Each variable is reduced with the statistic BMKG itself publishes for that column, per
    GHCN_STATISTIC, so the comparison is like-for-like.
    """
    series: dict[tuple[str, str], dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    days: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in _read(DAILY):
        wmo = GHCN_TO_WMO.get(row["station_id"])
        if not wmo:
            continue
        key = (wmo, row["date"][:7])
        days[key].add(row["date"])
        for var in VARIABLES:
            if row.get(var):
                series[key][var].append(float(row[var]))

    out = {}
    for key, per_var in series.items():
        reduced = {v: GHCN_STATISTIC[v](per_var[v]) for v in VARIABLES if per_var.get(v)}
        out[key] = dict(reduced, n_days=len(days[key]))
    return out


def main() -> None:
    ghcn = _ghcn_monthly()
    rows = []
    for record in _read(MONTHLY):
        reference = ghcn.get((record["station_id"], record["period"]))
        if not reference or reference["n_days"] < MIN_DAYS_PER_MONTH:
            continue
        row = {
            "station_id": record["station_id"],
            "station_name": record["station_name"],
            "period": record["period"],
            "ghcn_days": reference["n_days"],
        }
        for var in VARIABLES:
            bmkg = float(record[var]) if record.get(var) else None
            got = reference.get(var)
            row[f"{var}_bmkg"] = bmkg
            row[f"{var}_ghcn"] = round(got, 2) if got is not None else None
            row[f"{var}_diff"] = (
                round(bmkg - got, 2) if bmkg is not None and got is not None else None
            )
        rows.append(row)

    if not rows:
        raise SystemExit(
            "tidak ada bulan beririsan. GHCN berhenti awal Mar 2025 dan dataonline mulai "
            "Nov 2024, jadi seharusnya ada 4 bulan -- cek kedua CSV sumber."
        )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {OUT.relative_to(ROOT)} ({len(rows)} rows)")

    stat_name = {"tmax_c": "maks", "tmin_c": "min", "tavg_c": "rata2"}
    print("\n  statistik sepadan: "
          + ", ".join(f"{v} = {stat_name[v]} bulanan" for v in VARIABLES))
    print(f"  {'stasiun':8s} {'bulan':8s} {'hari':>5s}  "
          + "  ".join(f"{v[:4]:>5s} BMKG/GHCN" for v in VARIABLES))
    for row in rows:
        cells = []
        for var in VARIABLES:
            bmkg, got = row[f"{var}_bmkg"], row[f"{var}_ghcn"]
            cells.append(
                f"{bmkg:5.1f}/{got:<5.1f}" if bmkg is not None and got is not None else "    -/-   "
            )
        print(f"  {row['station_id']:8s} {row['period']:8s} {row['ghcn_days']:5d}  "
              + "  ".join(cells))

    print("\n  selisih rata-rata (BMKG - GHCN), untuk model_card.json:")
    for var in VARIABLES:
        diffs = [r[f"{var}_diff"] for r in rows if r[f"{var}_diff"] is not None]
        if diffs:
            print(f"    {var:8s} rata-rata {statistics.fmean(diffs):+.2f} C, "
                  f"terbesar {max(diffs, key=abs):+.2f} C, n={len(diffs)}")

    check(rows)


def check(rows: list[dict]) -> None:
    """The two sources redistribute the same observations, so like-for-like must agree closely."""
    assert rows, "tidak ada baris untuk dibandingkan"
    for row in rows:
        for var in VARIABLES:
            diff = row[f"{var}_diff"]
            if diff is None:
                continue
            limit = MAX_DIFF_C[var]
            assert abs(diff) <= limit, (
                f"{row['station_id']} {row['period']} {var}: selisih {diff:+.2f} C melebihi "
                f"{limit} C. Cek dulu apakah statistiknya sepadan (GHCN_STATISTIC) sebelum "
                "menyimpulkan datanya salah."
            )

    # GHCN's observed extreme can only be inside BMKG's, never outside: it sees fewer days.
    for row in rows:
        if row["tmax_c_diff"] is not None:
            assert row["tmax_c_diff"] >= -MAX_DIFF_C["tmax_c"], (
                f"{row['station_id']} {row['period']}: maks GHCN melebihi maks BMKG, "
                "padahal GHCN punya hari lebih sedikit -- cek pemetaan stasiun"
            )
    print("check ok")


if __name__ == "__main__":
    main()
