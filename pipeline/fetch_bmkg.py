"""Download daily air temperature for Jakarta BMKG synoptic stations (DATA_SOURCES.md §E).

Source: NOAA GHCN-Daily, which redistributes BMKG's own synoptic reports (WMO IDs
96745/96741/96749/96739). dataonline.bmkg.go.id holds the same station records but is
behind a login, so it cannot be fetched unattended — see docs/DECISIONS.md.

Run: uv run --no-project --python 3.12 python pipeline/fetch_bmkg.py
Output: data/raw/bmkg/stations_daily.csv (tidy, one row per station-day)
"""

import csv
import io
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "raw" / "bmkg" / "stations_daily.csv"

GHCN_CSV = "https://www.ncei.noaa.gov/data/global-historical-climatology-network-daily/access/{sid}.csv"

# DATA_SOURCES.md §E names Kemayoran, Tanjung Priok, Halim. Halim (96747) is absent from
# GHCN; Soekarno-Hatta and Budiarto are included as the nearest substitutes.
STATIONS = {
    "ID000096745": "Kemayoran (Jakarta Observatory)",
    "IDM00096741": "Tanjung Priok",
    "IDM00096749": "Soekarno-Hatta",
    "IDM00096739": "Budiarto (Curug)",
}

START_YEAR = 2023  # LST compositing window, CONCEPT §7.2
TENTHS_TO_C = 0.1
FIELDS = ["station_id", "station_name", "date", "lat", "lon", "tmax_c", "tmin_c", "tavg_c"]


def fetch(sid: str) -> str:
    req = urllib.request.Request(GHCN_CSV.format(sid=sid), headers={"User-Agent": "teduh-pipeline"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return r.read().decode("utf-8")


def to_celsius(raw: str) -> float | None:
    raw = raw.strip()
    return round(int(raw) * TENTHS_TO_C, 1) if raw else None


def station_rows(sid: str, name: str) -> list[dict]:
    rows = []
    for row in csv.DictReader(io.StringIO(fetch(sid))):
        date = row["DATE"]
        if int(date[:4]) < START_YEAR:
            continue
        temps = {
            "tmax_c": to_celsius(row["TMAX"]),
            "tmin_c": to_celsius(row["TMIN"]),
            "tavg_c": to_celsius(row["TAVG"]),
        }
        if not any(temps.values()):
            continue
        rows.append({
            "station_id": sid, "station_name": name, "date": date,
            "lat": row["LATITUDE"], "lon": row["LONGITUDE"], **temps,
        })
    return rows


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    all_rows = []
    for sid, name in STATIONS.items():
        rows = station_rows(sid, name)
        print(f"{name:34s} {len(rows):5d} days  {rows[0]['date'] if rows else '-'} .. {rows[-1]['date'] if rows else '-'}")
        all_rows += rows

    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(all_rows)
    print(f"wrote {OUT.relative_to(ROOT)} ({len(all_rows)} rows)")
    check(all_rows)


def check(rows: list[dict]) -> None:
    """Plausibility: Jakarta daily air temps sit well inside 15-45 C, tmin <= tmax."""
    assert rows, "no rows fetched"
    for r in rows:
        for k in ("tmax_c", "tmin_c", "tavg_c"):
            v = r[k]
            assert v is None or 15.0 <= v <= 45.0, f"implausible {k}={v} at {r['station_id']} {r['date']}"
        if r["tmin_c"] is not None and r["tmax_c"] is not None:
            assert r["tmin_c"] <= r["tmax_c"], f"tmin > tmax at {r['station_id']} {r['date']}"
    assert any(r["station_id"] == "ID000096745" for r in rows), "Kemayoran missing"
    print("check ok")


if __name__ == "__main__":
    main()
