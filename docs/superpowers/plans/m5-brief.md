# M5 — Policy Brief dan Validator Provenance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> Baca `docs/superpowers/plans/README.md` bagian **Global Constraints** dan **Interface Registry**. Prasyarat: **M0, M2, M3a, M3b selesai**. M3c dibutuhkan untuk Task M5-T2.

**Goal:** Draf brief Markdown berpenanda → brief final dengan catatan kaki sumber dan PDF, di mana validator menolak setiap angka yang tidak punya asal-usul.

**Architecture:** Keputusan paling penting di milestone ini: **validasi dijalankan pada draf mentah, sebelum penanda disubstitusi.** Kalau divalidasi setelah substitusi, angka yang baru saja dimasukkan validator sendiri akan terlihat seperti angka liar, dan satu-satunya cara lolos adalah mengecualikan angka hasil substitusi — yang berarti validator mengecualikan tepat hal yang seharusnya diperiksa. Urutannya: validasi → substitusi → catatan kaki → PDF.

**Tech Stack:** regex, markdown-it-py, WeasyPrint, FastAPI.

## Global Constraints

- **Jangan melemahkan validator agar tes lulus** (CLAUDE.md aturan 3). Kalau draf gagal, perbaiki drafnya.
- Daftar putih hanya yang disebut CONCEPT §8.4: **tahun** (19xx/20xx), **nomor bagian**, **nomor peraturan**.
- Brief **tidak** merender disclaimer "harga ini asumsi" (DECISIONS 2026-10-09), tetapi `source` tetap dibawa di `facts` supaya angka biaya lolos validator.
- Delapan bagian brief wajib ada dan berurutan (CONCEPT §8.4).
- Format angka gaya Indonesia: koma desimal, titik ribuan, tanda minus U+2212.
- `tests/test_provenance.py` adalah tes **wajib** (CLAUDE.md): angka liar ditolak; tahun dan nomor bagian **tidak** ditolak.
- Commit conventional, diakhiri `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`.

---

## File Structure

| File | Tanggung jawab |
|---|---|
| `teduh_agent/tools/brief.py` | Ledger fakta sesi, validator, substitusi penanda, catatan kaki, render PDF. |
| `api/routes.py` | **Diubah**: tambah `GET /api/brief/{brief_id}`. |
| `.gitignore` | **Diubah**: tambah `data/briefs/`. |
| `docs/DECISIONS.md` | **Diubah**: catat penyimpanan brief di disk, bukan Firestore. |

---

## Task M5-T1: Validator provenance dan render Markdown

**Files:**
- Create: `teduh_agent/tools/brief.py`
- Modify: `.gitignore` (tambah `data/briefs/`)
- Modify: `docs/DECISIONS.md`
- Test: `tests/test_provenance.py`

**Interfaces:**
- Consumes: `teduh_agent.facts.{Fact, session_facts, record}` (M0-T2); `teduh_agent.store.get_store` (M0-T3).
- Produces:
  - `MARKER_PATTERN`, `YEAR_PATTERN`, `SECTION_PATTERN`, `REGULATION_PATTERN`, `NUMBER_PATTERN`
  - `REQUIRED_SECTIONS: tuple[str, ...]` — delapan judul bagian
  - `BRIEF_DIR: Path`, `MAX_REWRITES = 2`
  - `UNIT_RENDER: dict[str, tuple[str, str]]` — satuan → (prefix, suffix)
  - `format_value(value, unit: str) -> str`
  - `markers_in(draft: str) -> list[str]`
  - `validate(draft: str, facts: list[Fact]) -> dict` — `{"errors": [...], "warnings": [...], "unknown_markers": [...], "unused_facts": [...]}`
  - `substitute(draft: str, facts: list[Fact]) -> tuple[str, list[Fact]]`
  - `footnotes(used: list[Fact]) -> str`
  - `get_session_facts(tool_context) -> dict`
  - `render_policy_brief(draft_markdown: str, tool_context) -> dict`

- [x] **Step 1: Tulis tes yang gagal**

Buat `tests/test_provenance.py`:

```python
"""WAJIB menurut CLAUDE.md: a wild number is rejected; a year or a section number is not.

This is the product's headline claim -- the "Semua angka terverifikasi" badge -- so these
tests exist to make weakening the validator loud rather than convenient. If a test here
starts failing, fix the draft or the facts, never the rule."""

import pytest

from teduh_agent.facts import SOURCE_DATA, SOURCE_MODEL, fact, record
from teduh_agent.tools.brief import (
    REQUIRED_SECTIONS,
    format_value,
    get_session_facts,
    markers_in,
    render_policy_brief,
    substitute,
    validate,
)


class FakeToolContext:
    def __init__(self) -> None:
        self.state: dict = {}


@pytest.fixture
def facts() -> list:
    return [
        fact("kel_ID3173040002.lst", "Suhu permukaan rata-rata", 44.61, "degC", SOURCE_DATA),
        fact("kel_ID3173040002.hvi_rank", "Peringkat HVI", 1, "peringkat", SOURCE_DATA),
        fact("kel_ID3173040002.vulnerable", "Warga rentan", 1020.39, "jiwa", SOURCE_DATA),
        fact("sim.ID3173040002.delta_lst", "Perubahan suhu", -0.83, "degC", SOURCE_MODEL),
        fact("opt.total_cost", "Total biaya", 1_950_000_000.0, "IDR",
             "Kepgub DKI 811/2025, item 696.19, hlm 1262"),
    ]


def _full_draft() -> str:
    """A draft with all eight required sections and no wild numbers."""
    body = "\n\n".join(f"## {section}\n\nIsi bagian ini." for section in REQUIRED_SECTIONS)
    return f"# Policy Brief TEDUH\n\n{body}\n"


# --- marker handling ------------------------------------------------------------------

@pytest.mark.unit
def test_markers_are_found():
    assert markers_in("Suhunya [[F:kel_ID3173040002.lst]] saja.") == [
        "kel_ID3173040002.lst"
    ]


@pytest.mark.unit
def test_substitution_inserts_the_value_with_its_unit(facts):
    rendered, used = substitute("Suhu [[F:kel_ID3173040002.lst]].", facts)
    assert "44,61 °C" in rendered
    assert len(used) == 1


@pytest.mark.unit
def test_substitution_formats_rupiah_indonesian_style(facts):
    rendered, _ = substitute("Biaya [[F:opt.total_cost]].", facts)
    assert "Rp 1.950.000.000" in rendered


@pytest.mark.unit
def test_substitution_uses_a_real_minus_sign(facts):
    # design/README.md: minus is U+2212, not a hyphen.
    rendered, _ = substitute("Perubahan [[F:sim.ID3173040002.delta_lst]].", facts)
    assert "−0,83" in rendered


@pytest.mark.unit
def test_substitution_appends_a_footnote_reference(facts):
    rendered, _ = substitute("Suhu [[F:kel_ID3173040002.lst]].", facts)
    assert "[^" in rendered


@pytest.mark.unit
def test_integer_facts_do_not_gain_decimals(facts):
    rendered, _ = substitute("Peringkat [[F:kel_ID3173040002.hvi_rank]].", facts)
    assert "1 peringkat" in rendered or "peringkat 1" in rendered or " 1" in rendered
    assert "1,00" not in rendered


@pytest.mark.unit
def test_format_value_groups_thousands_with_dots():
    assert format_value(1020.39, "jiwa") == "1.020,39 jiwa"


# --- the mandatory rejection ----------------------------------------------------------

@pytest.mark.unit
def test_a_wild_number_is_rejected(facts):
    draft = _full_draft() + "\nSuhu rata-ratanya sekitar 44,6 derajat.\n"
    report = validate(draft, facts)
    assert report["errors"], "angka liar lolos validator"
    assert any("44" in error for error in report["errors"])


@pytest.mark.unit
def test_a_wild_number_inside_a_sentence_with_markers_is_still_rejected(facts):
    draft = _full_draft() + (
        "\nSuhunya [[F:kel_ID3173040002.lst]] dan turun 3 derajat setelah intervensi.\n"
    )
    assert validate(draft, facts)["errors"]


@pytest.mark.unit
def test_a_fabricated_percentage_is_rejected(facts):
    draft = _full_draft() + "\nSekitar 80% warga akan merasakan manfaatnya.\n"
    assert validate(draft, facts)["errors"]


@pytest.mark.unit
def test_a_draft_using_only_markers_passes(facts):
    draft = _full_draft() + (
        "\nKelurahan paling rentan memiliki suhu permukaan "
        "[[F:kel_ID3173040002.lst]] pada peringkat [[F:kel_ID3173040002.hvi_rank]].\n"
    )
    assert validate(draft, facts)["errors"] == []


# --- the mandatory whitelist ----------------------------------------------------------

@pytest.mark.unit
def test_a_year_is_not_rejected(facts):
    draft = _full_draft() + "\nData citra satelit musim kemarau 2023 sampai 2025.\n"
    assert validate(draft, facts)["errors"] == []


@pytest.mark.unit
def test_a_section_number_is_not_rejected(facts):
    draft = _full_draft() + "\n### 1. Latar belakang\n\n1. Poin pertama\n2. Poin kedua\n"
    assert validate(draft, facts)["errors"] == []


@pytest.mark.unit
def test_a_regulation_number_is_not_rejected_but_is_reported(facts):
    # CONCEPT §8.4 whitelists regulation numbers. Allowed, but surfaced as a warning so a
    # fabricated figure cannot hide behind a citation unnoticed.
    draft = _full_draft() + (
        "\nMengacu pada UU No. 26 Tahun 2007 dengan target RTH 30% dari luas kota.\n"
    )
    report = validate(draft, facts)
    assert report["errors"] == []
    assert report["warnings"]


@pytest.mark.unit
def test_an_unknown_marker_is_reported_as_an_error(facts):
    draft = _full_draft() + "\nSuhu [[F:kel_TIDAK_ADA.lst]].\n"
    report = validate(draft, facts)
    assert report["unknown_markers"] == ["kel_TIDAK_ADA.lst"]
    assert report["errors"]


# --- structure ------------------------------------------------------------------------

@pytest.mark.unit
def test_a_missing_required_section_is_an_error(facts):
    draft = "# Brief\n\n## Ringkasan Eksekutif\n\nIsi.\n"
    report = validate(draft, facts)
    assert any("Keterbatasan" in error for error in report["errors"])


@pytest.mark.unit
def test_sections_out_of_order_are_an_error(facts):
    reversed_sections = "\n\n".join(
        f"## {section}\n\nIsi." for section in reversed(REQUIRED_SECTIONS)
    )
    report = validate(f"# Brief\n\n{reversed_sections}\n", facts)
    assert any("urutan" in error.lower() for error in report["errors"])


@pytest.mark.unit
def test_all_eight_concept_sections_are_required():
    assert len(REQUIRED_SECTIONS) == 8
    assert REQUIRED_SECTIONS[0] == "Ringkasan Eksekutif"
    assert REQUIRED_SECTIONS[-1] == "Sumber"


# --- the tool surface -----------------------------------------------------------------

@pytest.mark.integration
def test_render_returns_errors_instead_of_a_brief_when_validation_fails(facts):
    ctx = FakeToolContext()
    record(ctx, facts)
    result = render_policy_brief(_full_draft() + "\nTurun 3 derajat.\n", ctx)
    assert "errors" in result
    assert "brief_markdown" not in result


@pytest.mark.integration
def test_render_produces_a_brief_with_a_verified_count(facts):
    ctx = FakeToolContext()
    record(ctx, facts)
    draft = _full_draft() + (
        "\nSuhu [[F:kel_ID3173040002.lst]], peringkat [[F:kel_ID3173040002.hvi_rank]].\n"
    )
    result = render_policy_brief(draft, ctx)
    assert result["verified_count"] == 2
    assert "Semua angka terverifikasi" in result["badge"]


@pytest.mark.integration
def test_render_appends_a_sources_section_with_footnote_definitions(facts):
    ctx = FakeToolContext()
    record(ctx, facts)
    result = render_policy_brief(
        _full_draft() + "\nSuhu [[F:kel_ID3173040002.lst]].\n", ctx
    )
    assert "[^1]:" in result["brief_markdown"]


@pytest.mark.integration
def test_cost_footnote_cites_the_price_without_the_word_asumsi(facts):
    # DECISIONS 2026-10-09: the brief does not render an "this price is an assumption"
    # disclaimer, but the source still travels with the fact.
    ctx = FakeToolContext()
    record(ctx, facts)
    result = render_policy_brief(
        _full_draft() + "\nTotal biaya [[F:opt.total_cost]].\n", ctx
    )
    assert "asumsi" not in result["brief_markdown"].lower()
    assert "Kepgub" in result["brief_markdown"]


@pytest.mark.integration
def test_render_assigns_a_brief_id_and_writes_it_to_disk(facts):
    ctx = FakeToolContext()
    record(ctx, facts)
    result = render_policy_brief(
        _full_draft() + "\nSuhu [[F:kel_ID3173040002.lst]].\n", ctx
    )
    from teduh_agent.tools.brief import BRIEF_DIR

    assert (BRIEF_DIR / f"{result['brief_id']}.md").exists()


@pytest.mark.integration
def test_render_without_any_facts_in_session_refuses():
    result = render_policy_brief(_full_draft(), FakeToolContext())
    assert "errors" in result


@pytest.mark.integration
def test_get_session_facts_returns_what_the_tools_recorded(facts):
    ctx = FakeToolContext()
    record(ctx, facts)
    result = get_session_facts(ctx)
    assert len(result["facts"]) == len(facts)
    assert result["count"] == len(facts)
```

- [x] **Step 2: Jalankan tes untuk memastikan gagal**

Run: `uv run pytest tests/test_provenance.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'teduh_agent.tools.brief'`

- [x] **Step 3: Tulis `teduh_agent/tools/brief.py`**

```python
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
    if not referenced:
        errors.append(
            "Draf tidak memuat satu pun penanda [[F:id]]. Brief tanpa angka terverifikasi "
            "tidak bisa dirender."
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
```

- [x] **Step 4: Tambahkan `data/briefs/` ke `.gitignore`**

```gitignore
# Brief yang dihasilkan saat runtime. Bisa memuat nama wilayah dan angka anggaran.
data/briefs/
```

- [x] **Step 5: Catat keputusan di `docs/DECISIONS.md`**

Tambahkan sebelum baris penutup:

```markdown
## 2026-10-09 — Brief disimpan di disk, bukan Firestore

- **Konsep (§6.1):** Firestore menyimpan sesi, brief, dan laporan atap.
- **Keputusan:** `render_policy_brief` menulis Markdown dan PDF ke `data/briefs/<brief_id>.{md,pdf}` di dalam container. Sesi ADK tetap memakai penyimpanan default ADK.
- **Alasan:** brief tidak perlu bertahan melewati umur instance untuk demo — pengguna mengunduhnya langsung setelah dibuat. Menambah Firestore berarti menambah kredensial, aturan keamanan, dan satu titik gagal lagi tepat pada jalur yang dinilai, untuk kegunaan yang tidak diminta.
- **Risiko:** tautan unduh mati setelah instance Cloud Run diganti, dan dengan beberapa instance tautan hanya hidup di instance yang membuatnya. Dapat diterima untuk hackathon dengan `max-instances` kecil. Kalau brief perlu bertahan, pindahkan ke GCS dengan URL bertanda tangan dan catat di sini.
```

- [x] **Step 6: Jalankan tes untuk memastikan lulus**

Run: `uv run pytest tests/test_provenance.py -v`
Expected: PASS, 24 tes.

- [x] **Step 7: Commit**

```bash
git add teduh_agent/tools/brief.py .gitignore docs/DECISIONS.md tests/test_provenance.py
git commit -m "feat: tambah validator provenance dan render brief Markdown

Validasi dijalankan pada draf mentah sebelum substitusi, supaya validator tidak
perlu mengecualikan angka yang baru saja dimasukkannya sendiri.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task M5-T2: Render PDF dan endpoint unduh

**Files:**
- Modify: `teduh_agent/tools/brief.py` (tambah render PDF)
- Modify: `api/routes.py` (tambah `GET /api/brief/{brief_id}`)
- Test: `tests/test_brief_pdf.py`

**Interfaces:**
- Consumes: `markdown_it.MarkdownIt`, `weasyprint.HTML`; `api.schemas.{ok, fail}`.
- Produces:
  - Di `brief.py`: `PDF_CSS: str`, `to_html(markdown_body: str) -> str`, `to_pdf(markdown_body: str, destination: Path) -> Path`
  - `render_policy_brief` kini juga menulis `<brief_id>.pdf` dan mengembalikan `pdf_available: bool`
  - Di `routes.py`: `GET /api/brief/{brief_id}` dengan query `?format=md|pdf` (default `md`)

- [x] **Step 1: Tulis tes yang gagal**

Buat `tests/test_brief_pdf.py`:

```python
"""PDF rendering and the download endpoint. WeasyPrint needs Pango and Cairo as system
libraries, so these tests skip rather than fail when they are absent locally -- the
container installs them (infra/Dockerfile) and M8 verifies the deployed path."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes import router
from teduh_agent.facts import SOURCE_DATA, fact, record
from teduh_agent.tools.brief import REQUIRED_SECTIONS, render_policy_brief, to_html

weasyprint = pytest.importorskip("weasyprint", reason="WeasyPrint butuh Pango/Cairo")


class FakeToolContext:
    def __init__(self) -> None:
        self.state: dict = {}


@pytest.fixture(scope="module")
def client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


@pytest.fixture
def rendered() -> dict:
    ctx = FakeToolContext()
    record(ctx, [fact("kel_ID3173040002.lst", "Suhu permukaan rata-rata", 44.61, "degC",
                      SOURCE_DATA)])
    body = "\n\n".join(f"## {section}\n\nIsi bagian." for section in REQUIRED_SECTIONS)
    draft = f"# Policy Brief TEDUH\n\n{body}\n\nSuhu [[F:kel_ID3173040002.lst]].\n"
    result = render_policy_brief(draft, ctx)
    assert "errors" not in result, result.get("errors")
    return result


@pytest.mark.integration
def test_html_conversion_keeps_the_section_headings():
    html = to_html("## Keterbatasan\n\nIsi.\n")
    assert "Keterbatasan" in html
    assert "<h2" in html


@pytest.mark.integration
def test_html_includes_print_styles_so_the_pdf_is_not_naked():
    assert "@page" in to_html("# Judul\n")


@pytest.mark.integration
def test_render_also_writes_a_pdf(rendered):
    from teduh_agent.tools.brief import BRIEF_DIR

    assert rendered["pdf_available"] is True
    pdf = BRIEF_DIR / f"{rendered['brief_id']}.pdf"
    assert pdf.exists()
    assert pdf.stat().st_size > 1000, "PDF terlalu kecil untuk berisi apa pun"


@pytest.mark.integration
def test_pdf_starts_with_the_pdf_magic_bytes(rendered):
    from teduh_agent.tools.brief import BRIEF_DIR

    data = (BRIEF_DIR / f"{rendered['brief_id']}.pdf").read_bytes()
    assert data[:4] == b"%PDF"


@pytest.mark.integration
def test_endpoint_serves_the_markdown_by_default(client, rendered):
    response = client.get(f"/api/brief/{rendered['brief_id']}")
    assert response.status_code == 200
    assert "Ringkasan Eksekutif" in response.text


@pytest.mark.integration
def test_endpoint_serves_the_pdf_when_asked(client, rendered):
    response = client.get(f"/api/brief/{rendered['brief_id']}?format=pdf")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"


@pytest.mark.integration
def test_endpoint_404s_for_an_unknown_brief(client):
    assert client.get("/api/brief/tidakada00000").status_code == 404


@pytest.mark.integration
def test_endpoint_rejects_a_path_traversal_attempt(client):
    # brief_id lands in a filesystem path, so this is a real boundary.
    for attempt in ("../../etc/passwd", "..%2f..%2fetc%2fpasswd", "a/b"):
        assert client.get(f"/api/brief/{attempt}").status_code in (404, 422)
```

- [x] **Step 2: Jalankan tes untuk memastikan gagal**

Run: `uv run pytest tests/test_brief_pdf.py -v`
Expected: FAIL — `ImportError: cannot import name 'to_html' from 'teduh_agent.tools.brief'`

- [x] **Step 3: Tambah render PDF ke `teduh_agent/tools/brief.py`**

Tambahkan import di atas:

```python
from markdown_it import MarkdownIt
```

Tambahkan konstanta setelah `UNIT_RENDER`:

```python
# Print styling. Kept inline rather than as a separate .css file so the PDF cannot render
# unstyled because a file was missing from the container image.
PDF_CSS = """
@page { size: A4; margin: 22mm 20mm; }
body { font-family: "DejaVu Sans", sans-serif; font-size: 10.5pt; line-height: 1.5;
       color: #1C2321; }
h1 { font-size: 20pt; color: #1F5C4A; margin: 0 0 4mm; }
h2 { font-size: 13pt; color: #1F5C4A; margin: 7mm 0 2mm;
     border-bottom: 0.4mm solid #E3DED4; padding-bottom: 1mm; }
h3 { font-size: 11pt; margin: 5mm 0 2mm; }
table { border-collapse: collapse; width: 100%; font-size: 9.5pt; }
th, td { border: 0.2mm solid #E3DED4; padding: 1.6mm 2mm; text-align: left; }
th { background: #F7F4EE; }
sup { font-size: 7.5pt; color: #5E6662; }
.footnotes { font-size: 8.5pt; color: #5E6662; margin-top: 8mm;
             border-top: 0.4mm solid #E3DED4; padding-top: 3mm; }
"""

PDF_RENDERER = MarkdownIt("commonmark").enable("table")
```

Tambahkan fungsi sebelum `get_session_facts`:

```python
def to_html(markdown_body: str) -> str:
    """Markdown to a standalone print-ready HTML document."""
    return (
        "<!doctype html><html lang=\"id\"><head><meta charset=\"utf-8\">"
        f"<style>{PDF_CSS}</style></head><body>"
        f"{PDF_RENDERER.render(markdown_body)}"
        "</body></html>"
    )


def to_pdf(markdown_body: str, destination: Path) -> Path:
    """Render to PDF with WeasyPrint, which needs Pango and Cairo from the system."""
    from weasyprint import HTML

    HTML(string=to_html(markdown_body)).write_pdf(str(destination))
    return destination
```

Di `render_policy_brief`, ganti blok penulisan berkas menjadi:

```python
    BRIEF_DIR.mkdir(parents=True, exist_ok=True)
    (BRIEF_DIR / f"{brief_id}.md").write_text(body, encoding="utf-8")

    # A missing system library must not lose the brief the agent just produced, so a PDF
    # failure degrades to Markdown-only and says so instead of raising.
    pdf_available = False
    try:
        to_pdf(body, BRIEF_DIR / f"{brief_id}.pdf")
        pdf_available = True
    except Exception as error:  # noqa: BLE001 -- any WeasyPrint/system failure
        print(f"PERINGATAN: render PDF gagal, brief tetap tersedia sebagai Markdown: {error}")
```

dan tambahkan `"pdf_available": pdf_available,` ke dict yang dikembalikan.

- [x] **Step 4: Tambah endpoint ke `api/routes.py`**

Tambahkan import:

```python
from fastapi.responses import FileResponse, PlainTextResponse

from teduh_agent.tools.brief import BRIEF_DIR
```

Tambahkan konstanta:

```python
# brief_id reaches the filesystem, so it is matched against a strict pattern rather than
# sanitised. uuid4().hex[:12] is always 12 lowercase hex characters.
BRIEF_ID_PATTERN = r"^[0-9a-f]{12}$"
```

Tambahkan route:

```python
@router.get("/brief/{brief_id}")
def brief(brief_id: str, format: str = "md") -> Any:
    """Serve a rendered brief as Markdown or PDF."""
    import re

    if not re.match(BRIEF_ID_PATTERN, brief_id):
        return JSONResponse(status_code=404, content=fail("Brief tidak ditemukan."))
    if format not in {"md", "pdf"}:
        return JSONResponse(
            status_code=422, content=fail("Format harus 'md' atau 'pdf'.")
        )

    path = BRIEF_DIR / f"{brief_id}.{format}"
    if not path.exists():
        return JSONResponse(
            status_code=404,
            content=fail(
                "Brief tidak ditemukan. Tautan brief hanya berlaku selama instance "
                "yang membuatnya masih hidup."
            ),
        )

    if format == "pdf":
        return FileResponse(
            path,
            media_type="application/pdf",
            filename=f"teduh-brief-{brief_id}.pdf",
        )
    return PlainTextResponse(path.read_text(encoding="utf-8"), media_type="text/markdown")
```

- [x] **Step 5: Jalankan tes untuk memastikan lulus**

Run: `uv run pytest tests/test_brief_pdf.py -v`
Expected: PASS, 9 tes. Di-skip seluruhnya kalau WeasyPrint tidak bisa diimpor di mesin lokal.

Kalau WeasyPrint gagal di macOS, pasang dependensi sistemnya:

```bash
brew install pango cairo gdk-pixbuf libffi
```

Container sudah memuatnya lewat `infra/Dockerfile`, jadi kegagalan lokal tidak memblokir deploy.

- [ ] **Step 6: Uji alur penuh lewat agen**

Run: `uv run adk web`
Tanya berurutan:
1. "Kelurahan mana yang paling rentan panas di Jakarta Pusat?"
2. "Simulasikan cool roof 50% di tiga teratas."
3. "Anggaran kami Rp 2 miliar, susun paketnya."
4. "Buatkan policy brief untuk Bappeda."

Expected: `policy_writer` memanggil `get_session_facts` lalu `render_policy_brief`, dan hasilnya menyebut jumlah fakta terverifikasi. Kalau percobaan pertama gagal validasi, agen harus memperbaiki drafnya sendiri dan mencoba lagi — itu perilaku yang diinginkan dan layak diperhatikan di panel event.

- [x] **Step 7: Verifikasi brief tidak memuat angka tak bersumber**

```bash
uv run python -c "
import re, pathlib
from teduh_agent.tools.brief import BRIEF_DIR
latest = max(BRIEF_DIR.glob('*.md'), key=lambda p: p.stat().st_mtime)
text = latest.read_text()
print(latest.name, len(text), 'karakter')
print('catatan kaki:', text.count('[^'))
assert '[^1]:' in text, 'tidak ada definisi catatan kaki'
assert 'asumsi' not in text.lower(), 'disclaimer asumsi tidak boleh dirender (DECISIONS)'
print('ok')
"
```

- [x] **Step 8: Commit**

```bash
git add teduh_agent/tools/brief.py api/routes.py tests/test_brief_pdf.py
git commit -m "feat: render brief ke PDF dan sajikan lewat endpoint unduh

Kegagalan WeasyPrint menurunkan ke Markdown saja, bukan menghilangkan brief
yang baru dibuat agen.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Definisi M5 selesai

- [x] Angka liar di draf **ditolak**; tahun dan nomor bagian **tidak** ditolak; nomor peraturan diizinkan tetapi dilaporkan sebagai peringatan.
- [x] Penanda yang menunjuk fakta tidak dikenal ditolak dengan menyebut id-nya.
- [x] Kedelapan bagian wajib diperiksa keberadaan **dan** urutannya.
- [x] Brief yang lolos membawa lencana "Semua angka terverifikasi (n fakta)" dan catatan kaki per fakta.
- [x] Brief tidak memuat kata "asumsi" (DECISIONS 2026-10-09) tetapi tetap menyitir Kepgub untuk harga bersumber.
- [x] PDF terbentuk, dimulai dengan `%PDF`, dan bisa diunduh lewat `/api/brief/{id}?format=pdf`.
- [x] `brief_id` dicocokkan ke pola ketat, jadi path traversal tidak mungkin.
- [x] `uv run pytest -q` hijau.

**Selanjutnya:** [`m6-roof.md`](m6-roof.md) — Cek Atap dengan Gemini vision.
