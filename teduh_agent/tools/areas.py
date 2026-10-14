"""Area lookup, profile, ranking, and SHAP drivers.

find_area joins kelurahan_metrics.parquet with the GeoJSON properties because kec_name and
kota_name exist ONLY in the boundary file. Without that join, "Jakarta Timur" -- the single
most likely thing a planner types -- matches nothing at all.

rank_priority_areas recomputes HVI from model/hvi.py when the caller supplies weights,
rather than reading the baked hvi column. The weights are a policy choice the UI exposes, and
a stale column would make the ranking disagree with the map.
"""

import difflib
import re
from functools import lru_cache

import pandas as pd
from google.adk.tools import ToolContext

from model.explain import top_drivers
from model.hvi import COMPONENT_COLUMNS, hvi, load_weights, rank
from teduh_agent.facts import SOURCE_DATA, SOURCE_MODEL, fact, record
from teduh_agent.store import get_store

SCOPE_ALL = "all"
DEFAULT_TOP_K = 10
MAX_TOP_K = 50

# difflib ratio below which a near-miss is not a match at all. High enough to reject a
# genuinely different city ("Surabaya" -> "Rawa Buaya" is 0.667, "Bandung" -> "Cijantung"
# is 0.625) while still accepting a real typo ("Kampong Rawa" -> "Kampung Rawa" is 0.917).
FUZZY_CUTOFF = 0.8

# Administrative prefixes a user types but the data does not store.
PREFIX_PATTERN = re.compile(r"^(kel\.?|kelurahan|kec\.?|kecamatan|kota|kab\.?|kabupaten)\s+")

# Model feature names are English; these are what the UI and the agent must say instead.
FEATURE_LABELS: dict[str, str] = {
    "albedo": "Albedo permukaan (daya pantul)",
    "ndvi": "Kerapatan vegetasi (NDVI)",
    "ndbi": "Indeks lahan terbangun (NDBI)",
    "ndwi": "Indeks kebasahan (NDWI)",
    "tree_frac": "Tutupan pohon",
    "built_frac": "Fraksi lahan terbangun",
    "water_frac": "Fraksi badan air",
    "roof_frac": "Fraksi atap bangunan",
    "bldg_h_mean": "Tinggi bangunan rata-rata",
    "elev_m": "Elevasi",
    "dist_coast_km": "Jarak ke pantai",
    "pop": "Kepadatan penduduk",
}


def _normalise(text: str) -> str:
    return PREFIX_PATTERN.sub("", text.strip().lower())


@lru_cache(maxsize=1)
def directory() -> pd.DataFrame:
    """Kelurahan metrics plus the two names that live only in the boundary file."""
    store = get_store()
    properties = pd.DataFrame(
        [feature["properties"] for feature in store.boundaries["features"]]
    ).set_index("kel_id")
    return store.kelurahan.join(properties[["kec_name", "kota_name"]], how="left")


def _rows_to_matches(frame: pd.DataFrame) -> list[dict]:
    return [
        {
            "kel_id": kel_id,
            "kel_name": row["kel_name"],
            "kec_id": row["kec_id"],
            "kec_name": row["kec_name"],
            "kota_id": row["kota_id"],
            "kota_name": row["kota_name"],
        }
        for kel_id, row in frame.iterrows()
    ]


def _scope_id_for(hit: pd.DataFrame, scope_type: str) -> str:
    if scope_type == "kelurahan":
        return str(hit.index[0])
    column = "kec_id" if scope_type == "kecamatan" else "kota_id"
    return str(hit.iloc[0][column])


def _find_result(
    hit: pd.DataFrame, scope_type: str, query: str, normalised: str, tool_context
) -> dict:
    facts = [
        fact(
            f"find.{normalised}.count",
            f"Jumlah wilayah cocok untuk {query!r}",
            len(hit),
            "wilayah",
            SOURCE_DATA,
        )
    ]
    record(tool_context, facts)
    return {
        "matches": _rows_to_matches(hit),
        "scope_type": scope_type,
        "scope_id": _scope_id_for(hit, scope_type),
        "facts": facts,
    }


def find_area(query: str, tool_context: ToolContext | None = None) -> dict:
    """Cari wilayah berdasarkan nama kelurahan, kecamatan, atau kota di DKI Jakarta.

    Pencocokan longgar, jadi salah ketik kecil masih ketemu. Gunakan tool ini lebih dulu
    setiap kali pengguna menyebut nama tempat, untuk mendapatkan kel_id yang dibutuhkan
    tool lain.

    Args:
        query: nama tempat yang disebut pengguna, misalnya "Kampung Rawa", "Pademangan",
            atau "Jakarta Timur".

    Returns:
        dict dengan `matches` (daftar wilayah beserta kel_id), `scope_type`
        ("kelurahan", "kecamatan", atau "kota"), `scope_id`, dan `facts`.
    """
    normalised = _normalise(query)
    if not normalised:
        return {"error": "Nama wilayah kosong.", "matches": [], "facts": []}

    frame = directory()

    # Exact match first, most-specific administrative level first. This ordering is what
    # stops "Pademangan" (a kecamatan) from being swallowed by "Pademangan Barat" (a
    # kelurahan) and "Jakarta Timur" (a kota) from being swallowed by any kelurahan.
    for column, scope_type in (
        ("kel_name", "kelurahan"),
        ("kec_name", "kecamatan"),
        ("kota_name", "kota"),
    ):
        values = frame[column].fillna("").str.lower().map(_normalise)
        hit = frame[values == normalised]
        if not hit.empty:
            return _find_result(hit, scope_type, query, normalised, tool_context)

    # Typo tolerance, kelurahan names only: a slip like "Kampong Rawa" still lands, while a
    # genuinely different city ("Bandung", "Surabaya") falls below the fuzzy cutoff.
    kel_values = frame["kel_name"].fillna("").str.lower().map(_normalise)
    close = difflib.get_close_matches(
        normalised, kel_values.unique().tolist(), n=1, cutoff=FUZZY_CUTOFF
    )
    if close:
        hit = frame[kel_values == close[0]]
        return _find_result(hit, "kelurahan", query, normalised, tool_context)

    return {
        "error": (
            f"Tidak ada wilayah bernama {query!r} di data TEDUH. "
            "Cakupan saat ini hanya DKI Jakarta daratan."
        ),
        "matches": [],
        "facts": [],
    }


def get_area_profile(kel_id: str, tool_context: ToolContext | None = None) -> dict:
    """Ambil profil panas dan kerentanan satu kelurahan.

    Berisi suhu permukaan rata-rata, selisihnya dari rata-rata kota, peringkat HVI,
    keempat komponen HVI, vegetasi, tutupan lahan, jumlah penduduk, dan jumlah warga
    rentan. Pakai find_area lebih dulu untuk mendapatkan kel_id.

    Args:
        kel_id: kode kelurahan 12 karakter, misalnya "ID3173040002".

    Returns:
        dict dengan `profile`, `total_kelurahan`, `map_highlight`, dan `facts`.
    """
    frame = directory()
    if kel_id not in frame.index:
        return {"error": f"Kelurahan {kel_id!r} tidak ada di data TEDUH.", "facts": []}

    store = get_store()
    row = frame.loc[kel_id]
    anomaly = float(row["lst_c_mean"]) - store.city_lst_mean
    vulnerable = float(row["pop_u5"]) + float(row["pop_65p"])

    prefix = f"kel_{kel_id}"
    numeric: list[tuple[str, str, float, str]] = [
        ("lst", "Suhu permukaan rata-rata", float(row["lst_c_mean"]), "degC"),
        ("lst_anomaly", "Selisih suhu permukaan dari rata-rata kota", anomaly, "degC"),
        ("hvi", "Indeks Kerentanan Panas (HVI)", float(row["hvi"]), ""),
        ("hvi_rank", "Peringkat HVI", int(row["hvi_rank"]), "peringkat"),
        ("ndvi", "Kerapatan vegetasi (NDVI)", float(row["ndvi_mean"]), ""),
        ("tree_frac", "Tutupan pohon", float(row["tree_frac_mean"]), "fraksi"),
        ("built_frac", "Fraksi lahan terbangun", float(row["built_frac_mean"]), "fraksi"),
        ("water_frac", "Fraksi badan air", float(row["water_frac_mean"]), "fraksi"),
        ("pop", "Jumlah penduduk", float(row["pop"]), "jiwa"),
        ("vulnerable", "Warga rentan (balita dan lansia)", vulnerable, "jiwa"),
        (
            "exposed_vulnerable",
            "Warga rentan di sel paling panas",
            float(row["exposed_vulnerable"]),
            "jiwa",
        ),
        ("H", "Komponen HVI: bahaya panas", float(row["H"]), ""),
        ("E", "Komponen HVI: keterpaparan", float(row["E"]), ""),
        ("S", "Komponen HVI: kepekaan", float(row["S"]), ""),
        ("A", "Komponen HVI: kurangnya kapasitas adaptif", float(row["A"]), ""),
    ]

    facts = [
        fact(f"{prefix}.{key}", label, value, unit, SOURCE_DATA)
        for key, label, value, unit in numeric
    ]
    facts.append(
        fact(
            "data.city_lst_mean",
            "Suhu permukaan rata-rata DKI Jakarta",
            store.city_lst_mean,
            "degC",
            SOURCE_DATA,
        )
    )
    record(tool_context, facts)

    return {
        "profile": {
            "kel_id": kel_id,
            "kel_name": row["kel_name"],
            "kec_name": row["kec_name"],
            "kota_name": row["kota_name"],
            **{key: value for key, _, value, _ in numeric},
        },
        "total_kelurahan": len(frame),
        "note": "Suhu permukaan (LST) dari Landsat 8/9, bukan suhu udara.",
        "note_key": "note.lst_surface",
        "map_highlight": [kel_id],
        "facts": facts,
    }


def _resolve_scope(frame: pd.DataFrame, scope: str) -> tuple[pd.DataFrame, str] | None:
    """Narrow the directory to a scope given either a code or a name."""
    if not scope or scope.lower() == SCOPE_ALL:
        return frame, SCOPE_ALL
    if scope in frame["kota_id"].values:
        return frame[frame["kota_id"] == scope], scope
    if scope in frame["kec_id"].values:
        return frame[frame["kec_id"] == scope], scope

    located = find_area(scope)
    if not located["matches"]:
        return None
    ids = [match["kel_id"] for match in located["matches"]]
    return frame.loc[ids], located["scope_id"]


def rank_priority_areas(
    scope: str = SCOPE_ALL,
    top_k: int = DEFAULT_TOP_K,
    weights: dict | None = None,
    tool_context: ToolContext | None = None,
) -> dict:
    """Urutkan kelurahan dari yang paling rentan terhadap panas (HVI tertinggi).

    Pakai tool ini untuk pertanyaan tentang prioritas, kelurahan terpanas, atau wilayah
    mana yang perlu ditangani lebih dulu. Bobot HVI bisa diubah kalau pengguna ingin
    menekankan aspek tertentu.

    Args:
        scope: "all" untuk seluruh DKI, atau nama/kode kota atau kecamatan.
        top_k: banyak kelurahan yang dikembalikan, maksimal 50.
        weights: opsional, bobot HVI {"wE": ..., "wS": ..., "wA": ...} yang harus
            berjumlah 1. Kalau kosong, memakai bobot default 0,4 / 0,3 / 0,3.

    Returns:
        dict dengan `areas` (urut peringkat), `weights` yang dipakai, `scope_id`,
        `map_highlight`, dan `facts`.
    """
    frame = directory()
    resolved = _resolve_scope(frame, scope)
    if resolved is None:
        return {
            "error": f"Wilayah {scope!r} tidak ada di data TEDUH (hanya DKI Jakarta).",
            "facts": [],
        }
    scoped, scope_id = resolved
    limit = max(1, min(int(top_k), MAX_TOP_K))

    store = get_store()
    active = load_weights(store.hvi_cfg) if weights is None else dict(weights)
    try:
        # Stored H/E/S/A are already percentiles over the whole city (CONCEPT 7.4). Re-deriving
        # them from `scoped` would re-percentile inside the scope, so the same kelurahan would
        # score differently depending on the question asked, and the chat would contradict the
        # map in the same frame. Custom weights still apply - to city-wide components.
        scores = hvi(scoped[list(COMPONENT_COLUMNS)], active)
    except (KeyError, ValueError) as error:
        return {"error": f"Bobot HVI tidak valid: {error}", "facts": []}

    ranked = scoped.assign(hvi_scoped=scores, rank_scoped=rank(scores))
    ranked = ranked.nsmallest(limit, "rank_scoped")

    areas: list[dict] = []
    facts = []
    for position, (kel_id, row) in enumerate(ranked.iterrows(), start=1):
        areas.append(
            {
                "rank": position,
                "kel_id": kel_id,
                "kel_name": row["kel_name"],
                "kec_name": row["kec_name"],
                "kota_id": row["kota_id"],
                "kota_name": row["kota_name"],
                "hvi": float(row["hvi_scoped"]),
                "lst_c_mean": float(row["lst_c_mean"]),
                "tree_frac": float(row["tree_frac_mean"]),
                "exposed_vulnerable": float(row["exposed_vulnerable"]),
            }
        )
        label = f"HVI {row['kel_name']} (peringkat {position})"
        facts.append(
            fact(
                f"rank.{scope_id}.{position}.hvi",
                label,
                float(row["hvi_scoped"]),
                "",
                SOURCE_DATA,
            )
        )

    for key, value in active.items():
        facts.append(
            fact(f"rank.{scope_id}.weight.{key}", f"Bobot HVI {key}", float(value), "",
                 SOURCE_DATA)
        )
    record(tool_context, facts)

    return {
        "areas": areas,
        "weights": active,
        "scope_id": scope_id,
        "n_in_scope": len(scoped),
        "map_highlight": [area["kel_id"] for area in areas],
        "facts": facts,
    }


def explain_drivers(kel_id: str, tool_context: ToolContext | None = None) -> dict:
    """Jelaskan faktor apa yang membuat satu kelurahan panas, menurut model (SHAP).

    Mengembalikan tiga sampai lima faktor terbesar beserta besarnya kontribusi dalam
    derajat Celsius dan arahnya (memanaskan atau mendinginkan). Pakai tool ini kalau
    pengguna bertanya KENAPA sebuah wilayah panas, bukan hanya seberapa panas.

    Args:
        kel_id: kode kelurahan 12 karakter, misalnya "ID3173040002".

    Returns:
        dict dengan `drivers`, `pred_lst_c`, `map_highlight`, dan `facts`.
    """
    store = get_store()
    if store.shap_by_kel is None:
        return {
            "error": (
                "Penjelasan faktor pendorong belum tersedia karena artefak SHAP belum "
                "dibuat. Jalankan model.explain lebih dulu."
            ),
            "facts": [],
        }

    table = store.shap_by_kel.set_index("kel_id")
    if kel_id not in table.index:
        return {"error": f"Kelurahan {kel_id!r} tidak ada di tabel SHAP.", "facts": []}

    row = table.loc[kel_id]
    drivers = [
        {**driver, "label": FEATURE_LABELS.get(driver["feature"], driver["feature"])}
        for driver in top_drivers(row)
    ]

    facts = [
        fact(
            f"driver.{kel_id}.{driver['feature']}",
            f"Kontribusi {driver['label']} terhadap suhu permukaan",
            driver["contribution_c"],
            "degC",
            SOURCE_MODEL,
        )
        for driver in drivers
    ]
    facts.append(
        fact(
            f"kel_{kel_id}.pred_lst",
            "Suhu permukaan hasil prediksi model",
            float(row["pred_lst_c"]),
            "degC",
            SOURCE_MODEL,
        )
    )
    record(tool_context, facts)

    return {
        "drivers": drivers,
        "pred_lst_c": float(row["pred_lst_c"]),
        "note": (
            "Kontribusi dari model LightGBM (SHAP) dan bersifat korelasional, "
            "bukan sebab-akibat."
        ),
        "note_key": "note.shap_correlational",
        "map_highlight": [kel_id],
        "facts": facts,
    }
