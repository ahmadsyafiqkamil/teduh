"""Policy brief rendering with a number-provenance validator (CONCEPT §8.4).

The order of operations is the whole design, so it is worth stating plainly: VALIDATE the
raw draft first, with the markers still in place, and only then substitute. Validating after
substitution would mean the values the renderer just inserted look exactly like wild
numbers, and the only way to pass would be to exempt substituted text -- which exempts
precisely what needs checking. Validating first makes the rule simple and unfakeable: strip
the markers out, and whatever digits remain were written by the model from nothing.

The whitelist is kept to what CONCEPT §8.4 actually allows: years, section numbers, and
regulation numbers. Regulation numbers are the loosest of the three, because a legal target
figure (RTH 30%) is part of the citation rather than an attributable measurement. Those
lines pass but are returned as `warnings`, so a fabricated figure cannot hide behind a
citation without anyone seeing it.

Briefs are written to data/briefs/ rather than Firestore; see docs/DECISIONS.md.
"""

import re
import uuid
from pathlib import Path

from google.adk.tools import ToolContext

from teduh_agent.facts import Fact, session_facts
from teduh_agent.store import get_store

ROOT = Path(__file__).resolve().parents[2]
BRIEF_DIR = ROOT / "data" / "briefs"

MARKER_PATTERN = re.compile(r"\[\[F:([A-Za-z0-9_.\-]+)\]\]")

# Any run of digits, including Indonesian-formatted numbers and percentages.
NUMBER_PATTERN = re.compile(r"\d+(?:[.,]\d+)*\s*%?")

# Whitelist, exactly the three exceptions CONCEPT §8.4 grants.
YEAR_PATTERN = re.compile(r"^(19|20)\d{2}$")
SECTION_PATTERN = re.compile(r"^\s*(?:#{1,6}\s*)?\d+[.)]\s")
REGULATION_PATTERN = re.compile(
    r"\b(UU|PP|Perpres|Permen\w*|Pergub|Kepgub|Perda|Perwal|SNI|RDTR|RPJMD|RTRW)\b",
    re.IGNORECASE,
)

# CONCEPT §8.4, in order. Both presence and order are enforced.
REQUIRED_SECTIONS: tuple[str, ...] = (
    "Ringkasan Eksekutif",
    "Kondisi Panas Wilayah",
    "Kelompok Rentan",
    "Opsi Intervensi dan Perkiraan Dampak",
    "Rekomendasi Portofolio dan Anggaran",
    "Keterkaitan dengan Dokumen Perencanaan",
    "Keterbatasan",
    "Sumber",
)

MAX_REWRITES = 2

MINUS = "−"

# unit -> (prefix, suffix). Units the UI renders without a space keep an empty suffix.
UNIT_RENDER: dict[str, tuple[str, str]] = {
    "degC": ("", " °C"),
    "IDR": ("Rp ", ""),
    "jiwa": ("", " jiwa"),
    "m2": ("", " m²"),
    "kelurahan": ("", " kelurahan"),
    "paket": ("", " paket"),
    "peringkat": ("", ""),
    "fraksi": ("", ""),
    "%": ("", "%"),
    "": ("", ""),
}

SOURCE_CITATIONS = {
    "data:grid_features@v1": (
        "Data TEDUH v1: suhu permukaan Landsat 8/9 Collection 2 (median musim kemarau "
        "Juni-September 2023-2025), indeks vegetasi Sentinel-2, tutupan lahan ESA "
        "WorldCover v200, bangunan Google Open Buildings Temporal v1, penduduk WorldPop "
        "2025, elevasi Copernicus DEM GLO-30, batas kelurahan HDX COD-AB Indonesia."
    ),
    "model:lgbm@v1": (
        "Model panas TEDUH LightGBM v1 dengan monotonic constraints dan spatial block "
        "cross-validation. Rincian metrik dan keterbatasan ada di model card."
    ),
}

# Deliberately avoids the word "asumsi": DECISIONS 2026-10-09 removed that disclaimer from
# the brief at the project owner's request. The source still travels inside the Fact.
ASSUMPTION_CITATION = "Harga satuan TEDUH, dapat disesuaikan (config/costs.yaml)."


def format_value(value: float | int | str, unit: str) -> str:
    """Indonesian number formatting: comma decimal, dot thousands, U+2212 minus."""
    prefix, suffix = UNIT_RENDER.get(unit, ("", f" {unit}" if unit else ""))

    if isinstance(value, str):
        return f"{prefix}{value}{suffix}"

    negative = value < 0
    magnitude = abs(value)
    if isinstance(value, int) or float(magnitude).is_integer():
        body = f"{int(magnitude):,}".replace(",", ".")
    else:
        body = f"{magnitude:,.2f}".replace(",", "\x00").replace(".", ",").replace("\x00", ".")

    return f"{MINUS if negative else ''}{prefix}{body}{suffix}"


def markers_in(draft: str) -> list[str]:
    """Every fact id referenced by the draft, in order of appearance."""
    return MARKER_PATTERN.findall(draft)


def _section_headings(draft: str) -> list[str]:
    headings = []
    for line in draft.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            headings.append(stripped.lstrip("#").strip())
    return headings


def _structure_errors(draft: str) -> list[str]:
    headings = _section_headings(draft)
    errors: list[str] = []

    missing = [section for section in REQUIRED_SECTIONS if section not in headings]
    if missing:
        errors.append(f"Bagian wajib belum ada: {', '.join(missing)}.")
        return errors

    positions = [headings.index(section) for section in REQUIRED_SECTIONS]
    if positions != sorted(positions):
        errors.append(
            "Urutan bagian tidak sesuai. Urutan wajib: " + " > ".join(REQUIRED_SECTIONS) + "."
        )
    return errors


def _wild_numbers(draft: str) -> tuple[list[str], list[str]]:
    """Digits written outside a marker, split into hard errors and citation warnings."""
    stripped = MARKER_PATTERN.sub(" ", draft)
    errors: list[str] = []
    warnings: list[str] = []

    for line in stripped.splitlines():
        if SECTION_PATTERN.match(line):
            continue
        is_citation_line = bool(REGULATION_PATTERN.search(line))
        for token in NUMBER_PATTERN.findall(line):
            bare = token.strip().rstrip("%")
            if YEAR_PATTERN.match(bare):
                continue
            message = f"Angka {token.strip()!r} pada baris: {line.strip()[:90]!r}"
            if is_citation_line:
                warnings.append(message + " (diizinkan sebagai nomor peraturan)")
            else:
                errors.append(message)
    return errors, warnings


def validate(draft: str, facts: list[Fact]) -> dict:
    """Check structure, marker resolution, and the absence of unattributed numbers."""
    known = {entry["id"] for entry in facts}
    referenced = markers_in(draft)
    unknown = [marker for marker in dict.fromkeys(referenced) if marker not in known]

    errors = _structure_errors(draft)
    number_errors, warnings = _wild_numbers(draft)
    errors.extend(number_errors)

    if unknown:
        errors.append(
            "Penanda menunjuk fakta yang tidak ada di sesi ini: " + ", ".join(unknown) + ". "
            "Panggil tool yang menyediakan angka itu lebih dulu."
        )

    return {
        "errors": errors,
        "warnings": warnings,
        "unknown_markers": unknown,
        "unused_facts": sorted(known - set(referenced)),
    }


def substitute(draft: str, facts: list[Fact]) -> tuple[str, list[Fact]]:
    """Replace every marker with its formatted value plus a footnote reference."""
    by_id = {entry["id"]: entry for entry in facts}
    used: list[Fact] = []
    numbering: dict[str, int] = {}

    def _replace(match: re.Match) -> str:
        fact_id = match.group(1)
        entry = by_id[fact_id]
        if fact_id not in numbering:
            numbering[fact_id] = len(numbering) + 1
            used.append(entry)
        return f"{format_value(entry['value'], entry['unit'])}[^{numbering[fact_id]}]"

    return MARKER_PATTERN.sub(_replace, draft), used


def _citation_for(source: str) -> str:
    if source in SOURCE_CITATIONS:
        return SOURCE_CITATIONS[source]
    if source.startswith("evidence:"):
        evidence_id = source.split(":", 1)[1]
        for entry in get_store().evidence:
            if entry["id"] == evidence_id:
                authors = entry.get("source_authors") or ""
                journal = entry.get("source_journal") or ""
                parts = [part for part in (authors, entry["source_title"], journal,
                                           str(entry["year"]), entry["url_or_doi"]) if part]
                return ". ".join(parts)
        return f"Entri bukti {evidence_id} tidak ditemukan di basis bukti."
    if source.startswith("assumption:") or source.strip().upper() == "ASUMSI":
        return ASSUMPTION_CITATION
    # A literal citation string, e.g. the Kepgub reference carried by a price.
    return source


def footnotes(used: list[Fact]) -> str:
    """Footnote definitions in marker order, one per distinct fact."""
    lines = []
    for index, entry in enumerate(used, start=1):
        lines.append(f"[^{index}]: {entry['label']}. {_citation_for(entry['source'])}")
    return "\n".join(lines)


def get_session_facts(tool_context: ToolContext) -> dict:
    """Ambil semua fakta yang sudah terbukti di percakapan ini.

    Panggil tool ini sebelum menulis brief. Hanya angka yang muncul di daftar ini yang
    boleh dipakai, dan penanda [[F:id]] harus memakai `id` persis seperti di sini.

    Returns:
        dict dengan `facts` (daftar fakta berisi id, label, value, unit, source) dan
        `count`.
    """
    collected = session_facts(tool_context)
    return {"facts": collected, "count": len(collected)}


def render_policy_brief(draft_markdown: str, tool_context: ToolContext) -> dict:
    """Validasi dan render draf brief menjadi brief final dengan catatan kaki sumber.

    Draf harus memakai penanda [[F:id]] untuk SETIAP angka. Validator menolak angka yang
    ditulis langsung, kecuali tahun, nomor bagian, dan nomor peraturan.

    Args:
        draft_markdown: draf brief dalam Markdown dengan penanda [[F:id]], memuat
            kedelapan bagian wajib secara berurutan.

    Returns:
        Kalau lolos: dict dengan `brief_id`, `brief_markdown`, `verified_count`, `badge`,
        dan `warnings`. Kalau gagal: dict dengan `errors` berisi daftar perbaikan yang
        harus dilakukan, dan `facts_available`.
    """
    facts = session_facts(tool_context)
    if not facts:
        return {
            "errors": [
                "Belum ada fakta di sesi ini. Jalankan analisis dan simulasi lebih dulu "
                "supaya ada angka yang bisa dirujuk."
            ],
            "facts_available": 0,
        }

    report = validate(draft_markdown, facts)
    if report["errors"]:
        return {
            "errors": report["errors"],
            "warnings": report["warnings"],
            "facts_available": len(facts),
            "hint": (
                "Ganti setiap angka yang ditulis langsung menjadi penanda [[F:id]], atau "
                "hapus klaimnya kalau tidak ada faktanya. Maksimal "
                f"{MAX_REWRITES} kali percobaan ulang."
            ),
        }

    rendered, used = substitute(draft_markdown, facts)
    brief_id = uuid.uuid4().hex[:12]
    body = f"{rendered.rstrip()}\n\n{footnotes(used)}\n"

    BRIEF_DIR.mkdir(parents=True, exist_ok=True)
    (BRIEF_DIR / f"{brief_id}.md").write_text(body, encoding="utf-8")

    return {
        "brief_id": brief_id,
        "brief_markdown": body,
        "verified_count": len(used),
        "badge": f"Semua angka terverifikasi ({len(used)} fakta)",
        "warnings": report["warnings"],
        "unused_facts": report["unused_facts"],
        "download_path": f"/api/brief/{brief_id}",
    }
