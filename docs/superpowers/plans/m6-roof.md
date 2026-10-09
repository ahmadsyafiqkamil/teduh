# M6 — Cek Atap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> Baca `docs/superpowers/plans/README.md` bagian **Global Constraints** dan **Interface Registry**. Prasyarat: **M0 selesai**; M3c dibutuhkan untuk Task M6-T2. Bisa dikerjakan paralel dengan M4 dan M5.

**Goal:** Warga mengunggah foto atap dari ponsel, Gemini vision mengklasifikasinya ke skema terstruktur, dan sistem memberi rekomendasi **berbasis aturan** beserta peringatan keselamatan asbes.

**Architecture:** Pembagian tugasnya tegas dan merupakan inti desain: **Gemini hanya melihat, aturan yang memutuskan.** `analyze_roof_photo` mengembalikan deskripsi atap dan tidak pernah merekomendasikan apa pun; `recommend_roof_action` adalah fungsi murni tanpa LLM. Itulah sebabnya peringatan asbes bisa dijamin — kalau rekomendasi berasal dari model bahasa, peringatan paling penting di produk ini bisa hilang pada satu panggilan yang tidak beruntung.

**Tech Stack:** google-genai (`response_schema`), Pillow (hapus metadata), FastAPI `UploadFile`.

## Global Constraints

- **`recommend_roof_action` tidak boleh memakai LLM** (CONCEPT §8.5). Murni aturan.
- **Asbes:** `asbestos_cement` → peringatan eksplisit jangan diamplas, dipotong, atau dibor. Ini tidak boleh opsional, tidak boleh di akhir, dan tidak boleh diparafrase oleh agen.
- `confidence < 0,6` atau `roof_visible: false` → minta foto ulang. Jangan menebak.
- **Privasi** (CLAUDE.md aturan 8): metadata dihapus sebelum disimpan, lokasi paling detail setingkat kelurahan dan hanya atas persetujuan, foto tidak pernah di-commit.
- Target akurasi (`roof_form` ≥ 85%, `material` ≥ 70%) **belum boleh diklaim** sampai 30 foto berlabel ada. Saat ini `data/roof_test/labels.csv` berisi 0 foto tim.
- Model dari env `TEDUH_MODEL`. Jangan hard-code.
- Commit conventional, diakhiri `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`.

---

## File Structure

| File | Tanggung jawab |
|---|---|
| `teduh_agent/tools/roof.py` | Skema vision, pemanggilan Gemini, dan mesin aturan rekomendasi. |
| `api/routes.py` | **Diubah**: tambah `POST /api/roof` dengan unggahan dan penghapusan metadata. |
| `pyproject.toml` | **Diubah**: `pillow` pindah dari grup `pipeline` ke dependensi runtime. |

---

## Task M6-T1: Analisis vision dan aturan rekomendasi

**Files:**
- Create: `teduh_agent/tools/roof.py`
- Test: `tests/test_roof.py`

**Interfaces:**
- Consumes: `teduh_agent.facts.{fact, record, source_evidence, SOURCE_MODEL}`; `teduh_agent.store.get_store`; `google.genai`.
- Produces:
  - `ROOF_SCHEMA: dict` — `response_schema` CONCEPT §8.5
  - `ROOF_FORMS`, `MATERIALS`, `COLOR_TONES`, `CONDITIONS`, `SHADE_LEVELS` — tuple nilai yang sah
  - `MIN_CONFIDENCE = 0.6`
  - `VISION_PROMPT: str`
  - `ASBESTOS_WARNING: str`
  - `Recommendation` — frozen dataclass `(action: str, priority: str, reason: str, safety: tuple[str, ...], evidence_ids: tuple[str, ...])`
  - `RETAKE_GUIDANCE: str`
  - `analyze_roof_photo(image_uri: str, tool_context=None) -> dict`
  - `analyze_roof_bytes(data: bytes, mime_type: str) -> dict` — bagian murni, dipakai endpoint
  - `recommend_roof_action(roof: dict, tool_context=None) -> dict`

- [ ] **Step 1: Tulis tes yang gagal**

Buat `tests/test_roof.py`:

```python
"""Cek Atap. Almost every test here targets recommend_roof_action, because that function is
the one that must never get it wrong: it is pure rules precisely so the asbestos warning
cannot be lost to an unlucky LLM sampling.

analyze_roof_photo needs a Gemini call and a real photo, so it is covered by the schema
tests plus M8's labelled evaluation, not here."""

import pytest

from teduh_agent.tools.roof import (
    ASBESTOS_WARNING,
    COLOR_TONES,
    CONDITIONS,
    MATERIALS,
    MIN_CONFIDENCE,
    ROOF_FORMS,
    ROOF_SCHEMA,
    SHADE_LEVELS,
    recommend_roof_action,
)


class FakeToolContext:
    def __init__(self) -> None:
        self.state: dict = {}


def _roof(**overrides) -> dict:
    roof = {
        "roof_visible": True,
        "roof_form": "pitched",
        "material": "clay_tile",
        "color_tone": "dark",
        "condition": "good",
        "shade_from_trees": "none",
        "confidence": 0.9,
        "notes": "",
    }
    roof.update(overrides)
    return roof


# --- schema ---------------------------------------------------------------------------

@pytest.mark.unit
def test_schema_declares_all_eight_concept_fields():
    assert set(ROOF_SCHEMA["properties"]) == {
        "roof_visible",
        "roof_form",
        "material",
        "color_tone",
        "condition",
        "shade_from_trees",
        "confidence",
        "notes",
    }


@pytest.mark.unit
def test_schema_enumerations_match_the_declared_tuples():
    properties = ROOF_SCHEMA["properties"]
    assert properties["roof_form"]["enum"] == list(ROOF_FORMS)
    assert properties["material"]["enum"] == list(MATERIALS)
    assert properties["color_tone"]["enum"] == list(COLOR_TONES)
    assert properties["condition"]["enum"] == list(CONDITIONS)
    assert properties["shade_from_trees"]["enum"] == list(SHADE_LEVELS)


@pytest.mark.unit
def test_schema_enums_match_the_labels_csv_vocabulary():
    # data/roof_test/labels.csv is graded against these exact strings in M8.
    assert "asbestos_cement" in MATERIALS
    assert "metal_sheet" in MATERIALS
    assert set(ROOF_FORMS) == {"flat", "pitched", "mixed", "unknown"}


# --- the safety rule that cannot be lost ----------------------------------------------

@pytest.mark.unit
def test_asbestos_always_produces_the_safety_warning():
    result = recommend_roof_action(_roof(material="asbestos_cement"))
    assert any("amplas" in line.lower() for line in result["recommendation"]["safety"])
    assert ASBESTOS_WARNING in result["recommendation"]["safety"]


@pytest.mark.unit
def test_asbestos_warning_is_the_first_safety_line():
    # A warning buried under three paragraphs of advice is a warning nobody reads.
    result = recommend_roof_action(_roof(material="asbestos_cement"))
    assert result["recommendation"]["safety"][0] == ASBESTOS_WARNING


@pytest.mark.unit
def test_asbestos_is_never_told_to_paint_or_plant_on_the_roof():
    action = recommend_roof_action(_roof(material="asbestos_cement"))["recommendation"]
    assert "cool_roof" not in action["action"]
    assert "green_roof" not in action["action"]


@pytest.mark.unit
def test_asbestos_wins_over_every_other_rule():
    # Flat asbestos would otherwise look like a green-roof candidate.
    action = recommend_roof_action(
        _roof(material="asbestos_cement", roof_form="flat")
    )["recommendation"]
    assert "green_roof" not in action["action"]


# --- the ordinary rules ---------------------------------------------------------------

@pytest.mark.unit
def test_pitched_tile_gets_cool_roof_paint():
    action = recommend_roof_action(_roof(roof_form="pitched",
                                         material="clay_tile"))["recommendation"]
    assert action["action"] == "cool_roof"


@pytest.mark.unit
def test_dark_metal_is_high_priority():
    # CONCEPT §8.5: "Prioritas tinggi untuk metal gelap."
    action = recommend_roof_action(
        _roof(roof_form="pitched", material="metal_sheet", color_tone="dark")
    )["recommendation"]
    assert action["action"] == "cool_roof"
    assert action["priority"] == "tinggi"


@pytest.mark.unit
def test_light_coloured_roof_is_lower_priority_than_dark():
    dark = recommend_roof_action(
        _roof(material="metal_sheet", color_tone="dark")
    )["recommendation"]
    light = recommend_roof_action(
        _roof(material="metal_sheet", color_tone="light")
    )["recommendation"]
    assert dark["priority"] == "tinggi"
    assert light["priority"] != "tinggi"


@pytest.mark.unit
def test_flat_concrete_slab_gets_green_roof_with_a_structural_caveat():
    action = recommend_roof_action(
        _roof(roof_form="flat", material="concrete_slab")
    )["recommendation"]
    assert action["action"] == "green_roof"
    assert any("beban" in line.lower() or "struktur" in line.lower()
               for line in action["safety"])


@pytest.mark.unit
def test_heavy_tree_shade_is_told_to_keep_the_trees():
    action = recommend_roof_action(
        _roof(shade_from_trees="heavy")
    )["recommendation"]
    assert action["action"] == "maintain_shade"
    assert "pohon" in action["reason"].lower()


@pytest.mark.unit
def test_low_confidence_asks_for_another_photo():
    result = recommend_roof_action(_roof(confidence=0.4))
    assert result["recommendation"]["action"] == "retake_photo"
    assert result["recommendation"]["reason"]


@pytest.mark.unit
def test_invisible_roof_asks_for_another_photo():
    result = recommend_roof_action(_roof(roof_visible=False))
    assert result["recommendation"]["action"] == "retake_photo"


@pytest.mark.unit
def test_retake_includes_angle_guidance():
    result = recommend_roof_action(_roof(roof_visible=False))
    assert "sudut" in result["guidance"].lower()


@pytest.mark.unit
def test_confidence_exactly_at_the_threshold_is_accepted():
    result = recommend_roof_action(_roof(confidence=MIN_CONFIDENCE))
    assert result["recommendation"]["action"] != "retake_photo"


# --- contract ------------------------------------------------------------------------

@pytest.mark.integration
def test_recommendation_cites_evidence_for_its_action():
    result = recommend_roof_action(_roof(roof_form="flat", material="concrete_slab"))
    assert result["recommendation"]["evidence_ids"]
    assert result["evidence"], "rekomendasi tanpa bukti pendukung"


@pytest.mark.integration
def test_recommendation_returns_facts_like_every_other_tool():
    result = recommend_roof_action(_roof())
    assert "facts" in result


@pytest.mark.unit
def test_rejects_a_payload_missing_required_fields():
    result = recommend_roof_action({"roof_form": "pitched"})
    assert "error" in result


@pytest.mark.unit
def test_rejects_an_out_of_vocabulary_material():
    result = recommend_roof_action(_roof(material="emas"))
    assert "error" in result


@pytest.mark.unit
def test_records_into_the_session_ledger():
    ctx = FakeToolContext()
    recommend_roof_action(_roof(), ctx)
    assert "facts" in ctx.state
```

- [ ] **Step 2: Jalankan tes untuk memastikan gagal**

Run: `uv run pytest tests/test_roof.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'teduh_agent.tools.roof'`

- [ ] **Step 3: Tulis `teduh_agent/tools/roof.py`**

```python
"""Cek Atap: Gemini describes the roof, rules decide what to do about it (CONCEPT §8.5).

That split is the design, not an implementation detail. analyze_roof_photo returns a
description and never recommends anything; recommend_roof_action is pure Python with no LLM
anywhere in it. The reason is the asbestos warning: a homeowner sanding an asbestos-cement
sheet releases fibres, and that warning must fire on every single asbestos photo. A rule
engine guarantees that. A language model, however well prompted, does not.

The rules are ordered so asbestos is checked before anything else. Flat asbestos sheeting
would otherwise match the green-roof branch and be told to add soil and plants to the one
material that must not be drilled into.
"""

import os
from dataclasses import asdict, dataclass

from google.adk.tools import ToolContext

from teduh_agent.facts import SOURCE_MODEL, fact, record, source_evidence
from teduh_agent.store import get_store

MODEL = os.environ.get("TEDUH_MODEL", "gemini-3.8-flash")

ROOF_FORMS = ("flat", "pitched", "mixed", "unknown")
MATERIALS = (
    "clay_tile",
    "concrete_tile",
    "metal_sheet",
    "concrete_slab",
    "asbestos_cement",
    "other",
    "unknown",
)
COLOR_TONES = ("light", "medium", "dark")
CONDITIONS = ("good", "worn", "damaged", "unknown")
SHADE_LEVELS = ("none", "partial", "heavy")

# Below this, the classification is not trustworthy enough to advise on (CONCEPT §8.5).
MIN_CONFIDENCE = 0.6

ROOF_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "roof_visible": {"type": "boolean"},
        "roof_form": {"type": "string", "enum": list(ROOF_FORMS)},
        "material": {"type": "string", "enum": list(MATERIALS)},
        "color_tone": {"type": "string", "enum": list(COLOR_TONES)},
        "condition": {"type": "string", "enum": list(CONDITIONS)},
        "shade_from_trees": {"type": "string", "enum": list(SHADE_LEVELS)},
        "confidence": {"type": "number"},
        "notes": {"type": "string"},
    },
    "required": [
        "roof_visible",
        "roof_form",
        "material",
        "color_tone",
        "condition",
        "shade_from_trees",
        "confidence",
        "notes",
    ],
}

REQUIRED_FIELDS = tuple(ROOF_SCHEMA["required"])

VISION_PROMPT = """\
Amati foto atap bangunan ini dan isi skema yang diminta. Kamu hanya MENDESKRIPSIKAN apa
yang terlihat; jangan memberi rekomendasi apa pun.

Panduan:
- roof_visible: false kalau atap tidak terlihat jelas atau yang terfoto bukan atap.
- roof_form: "flat" untuk atap beton datar, "pitched" untuk atap miring/limasan,
  "mixed" kalau keduanya ada dalam satu bangunan.
- material: perhatikan tekstur dan pola. Genteng tanah liat bergelombang dan kemerahan;
  genteng beton lebih rata dan kelabu; seng/metal bergelombang panjang dan mengkilap;
  pelat beton rata tanpa pola; asbes bergelombang, kelabu kusam, sering berlumut dan
  bertepi rapuh.
- color_tone: terang, sedang, atau gelap menurut yang terlihat di foto.
- condition: "worn" kalau ada lumut, pudar, atau kotor berat; "damaged" kalau ada
  pecah, bolong, atau bagian yang hilang.
- shade_from_trees: "heavy" kalau sebagian besar atap ternaungi pohon.
- confidence: 0 sampai 1, sejujurnya. Kalau foto gelap, kabur, atau terlalu jauh, beri
  nilai rendah. Lebih baik mengaku tidak yakin daripada menebak.
- notes: satu kalimat Bahasa Indonesia tentang apa yang terlihat. Jangan menyebut nama
  orang, alamat, nomor rumah, atau plat nomor meskipun terlihat.
"""

ASBESTOS_WARNING = (
    "JANGAN mengamplas, memotong, atau mengebor atap ini. Atap asbes melepaskan serat "
    "berbahaya kalau dirusak, dan seratnya terhirup. Konsultasikan ke tenaga profesional "
    "sebelum melakukan pekerjaan apa pun pada atap ini."
)

STRUCTURAL_CAVEAT = (
    "Green roof menambah beban cukup besar, terutama saat media tanamnya basah. "
    "Periksa kekuatan struktur ke tenaga ahli sebelum memasangnya."
)

RETAKE_GUIDANCE = (
    "Coba foto ulang dari sudut yang memperlihatkan bidang atap, bukan hanya tepinya: "
    "berdiri agak jauh, arahkan kamera sedikit ke atas, dan ambil saat terang. "
    "Pastikan tidak ada wajah, nomor rumah, atau plat nomor dalam foto."
)

# Evidence entries backing each action (data/evidence/interventions.json).
ACTION_EVIDENCE: dict[str, tuple[str, ...]] = {
    "cool_roof": ("ev_coolroof_id_surface",),
    "green_roof": ("ev_greenroof_id_surface",),
    "maintain_shade": ("ev_urban_greening_meta",),
    "consult_professional": ("ev_green_curtain_tokyo",),
}


@dataclass(frozen=True)
class Recommendation:
    """What to do, how urgent, why, and what not to do while doing it."""

    action: str
    priority: str
    reason: str
    safety: tuple[str, ...]
    evidence_ids: tuple[str, ...]


def _validate(roof: dict) -> str | None:
    missing = [field for field in REQUIRED_FIELDS if field not in roof]
    if missing:
        return f"Hasil analisis atap tidak lengkap, kurang: {', '.join(missing)}."

    vocabularies = {
        "roof_form": ROOF_FORMS,
        "material": MATERIALS,
        "color_tone": COLOR_TONES,
        "condition": CONDITIONS,
        "shade_from_trees": SHADE_LEVELS,
    }
    for field, allowed in vocabularies.items():
        if roof[field] not in allowed:
            return f"Nilai {field} tidak dikenal: {roof[field]!r}."
    return None


def _decide(roof: dict) -> Recommendation:
    """The rule table from CONCEPT §8.5, in priority order."""
    if not roof["roof_visible"] or float(roof["confidence"]) < MIN_CONFIDENCE:
        return Recommendation(
            action="retake_photo",
            priority="-",
            reason=(
                "Atap belum terlihat cukup jelas untuk dinilai, jadi rekomendasinya "
                "ditahan dulu daripada menebak."
            ),
            safety=(),
            evidence_ids=(),
        )

    # Asbestos first, deliberately: flat asbestos would otherwise match the green-roof
    # branch and be told to add soil and plants to a material that must not be drilled.
    if roof["material"] == "asbestos_cement":
        return Recommendation(
            action="consult_professional",
            priority="tinggi",
            reason=(
                "Atap terindikasi asbes. Pengecatan maupun green roof butuh pengerjaan "
                "pada permukaannya, dan itu tidak aman dilakukan sendiri. Opsi yang aman "
                "adalah menambah peneduh pohon atau green curtain di sekitar rumah."
            ),
            safety=(ASBESTOS_WARNING,),
            evidence_ids=ACTION_EVIDENCE["consult_professional"],
        )

    if roof["shade_from_trees"] == "heavy":
        return Recommendation(
            action="maintain_shade",
            priority="rendah",
            reason=(
                "Atap sudah ternaungi pohon, jadi tambahan cool roof atau green roof "
                "manfaatnya kecil. Yang paling berguna adalah menjaga pohon yang sudah ada."
            ),
            safety=(),
            evidence_ids=ACTION_EVIDENCE["maintain_shade"],
        )

    if roof["roof_form"] == "flat" and roof["material"] == "concrete_slab":
        return Recommendation(
            action="green_roof",
            priority="sedang",
            reason=(
                "Atap beton datar cocok untuk green roof, yang efektif menurunkan panas "
                "pada siang hari. Kalau struktur tidak memungkinkan, cat cool roof tetap "
                "pilihan yang baik."
            ),
            safety=(STRUCTURAL_CAVEAT,),
            evidence_ids=ACTION_EVIDENCE["green_roof"],
        )

    dark_metal = roof["material"] == "metal_sheet" and roof["color_tone"] == "dark"
    return Recommendation(
        action="cool_roof",
        priority="tinggi" if dark_metal else "sedang",
        reason=(
            "Atap metal berwarna gelap menyerap panas paling banyak, jadi cat pemantul "
            "panas memberi dampak terbesar di sini."
            if dark_metal
            else "Atap ini bisa dicat dengan cat pemantul panas (cool roof) untuk "
            "mengurangi panas yang masuk ke dalam rumah."
        ),
        safety=(),
        evidence_ids=ACTION_EVIDENCE["cool_roof"],
    )


def analyze_roof_bytes(data: bytes, mime_type: str) -> dict:
    """Classify a roof photo already in memory. Pure half, used by POST /api/roof."""
    from google import genai
    from google.genai import types

    client = genai.Client()
    response = client.models.generate_content(
        model=MODEL,
        contents=[
            types.Part.from_bytes(data=data, mime_type=mime_type),
            VISION_PROMPT,
        ],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=ROOF_SCHEMA,
            temperature=0.0,
        ),
    )

    import json

    return json.loads(response.text)


def analyze_roof_photo(image_uri: str, tool_context: ToolContext | None = None) -> dict:
    """Kenali bentuk dan material atap dari sebuah foto.

    Tool ini HANYA mendeskripsikan atap. Untuk mendapatkan rekomendasi, lanjutkan dengan
    recommend_roof_action memakai hasilnya.

    Args:
        image_uri: lokasi foto, berupa path lokal atau URI gs:// yang sudah diunggah.

    Returns:
        dict dengan `roof` (delapan field terstruktur) dan `facts`.
    """
    from pathlib import Path

    path = Path(image_uri)
    if not path.exists():
        return {
            "error": (
                f"Foto {image_uri!r} tidak bisa dibaca. Unggah foto lewat halaman "
                "Cek Atap lebih dulu."
            ),
            "facts": [],
        }

    suffix = path.suffix.lower()
    mime_type = "image/png" if suffix == ".png" else "image/jpeg"
    try:
        roof = analyze_roof_bytes(path.read_bytes(), mime_type)
    except Exception as error:  # noqa: BLE001 -- any genai/network failure
        return {"error": f"Analisis foto gagal: {error}", "facts": []}

    facts = [
        fact(
            "roof.confidence",
            "Tingkat keyakinan analisis foto atap",
            float(roof.get("confidence", 0.0)),
            "",
            SOURCE_MODEL,
        )
    ]
    record(tool_context, facts)
    return {"roof": roof, "facts": facts}


def recommend_roof_action(roof: dict, tool_context: ToolContext | None = None) -> dict:
    """Beri rekomendasi pendinginan atap berdasarkan hasil analisis foto.

    Rekomendasi berasal dari aturan tetap, bukan dari penilaian bahasa, supaya peringatan
    keselamatan selalu muncul ketika seharusnya muncul.

    Args:
        roof: hasil `analyze_roof_photo`, berisi delapan field terstruktur.

    Returns:
        dict dengan `recommendation` (action, priority, reason, safety, evidence_ids),
        `evidence` bersitasi, `guidance` kalau perlu foto ulang, dan `facts`.
    """
    problem = _validate(roof)
    if problem:
        return {"error": problem, "facts": []}

    decision = _decide(roof)
    store = get_store()
    evidence = [
        entry for entry in store.evidence if entry["id"] in decision.evidence_ids
    ]

    facts = [
        fact(
            f"roof.evidence.{entry['id']}.min",
            f"{entry['source_title']} ({entry['year']}), batas bawah",
            entry["value_min"],
            entry["unit"],
            source_evidence(entry["id"]),
        )
        for entry in evidence
    ]
    record(tool_context, facts)

    return {
        "recommendation": asdict(decision)
        | {"safety": list(decision.safety), "evidence_ids": list(decision.evidence_ids)},
        "evidence": evidence,
        "guidance": RETAKE_GUIDANCE if decision.action == "retake_photo" else "",
        "facts": facts,
    }
```

- [ ] **Step 4: Jalankan tes untuk memastikan lulus**

Run: `uv run pytest tests/test_roof.py -v`
Expected: PASS, 22 tes.

Catatan: `asdict(decision)` mengubah tuple menjadi tuple; dict union setelahnya mengubah `safety` dan `evidence_ids` menjadi list agar JSON-nya bersih. Tes `test_asbestos_warning_is_the_first_safety_line` mengandalkan urutan itu.

- [ ] **Step 5: Aktifkan sub-agen `roof_inspector`**

Setelah modul ini ada, `teduh_agent/sub_agents/build_all()` (M4-T2) akan otomatis memuat `roof_inspector`, dan `ALL_TOOLS` akan memuat kedua tool ini.

Run: `uv run pytest tests/test_sub_agents.py -v`
Expected: tes `roof_inspector` tidak lagi di-skip.

- [ ] **Step 6: Commit**

```bash
git add teduh_agent/tools/roof.py tests/test_roof.py
git commit -m "feat: tambah Cek Atap dengan vision terstruktur dan rekomendasi berbasis aturan

Peringatan asbes diperiksa sebelum aturan lain, jadi atap asbes datar tidak bisa
direkomendasikan green roof.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task M6-T2: Endpoint unggah foto

**Files:**
- Modify: `pyproject.toml` (`pillow` ke dependensi runtime)
- Modify: `api/routes.py` (tambah `POST /api/roof`)
- Modify: `docs/DECISIONS.md`
- Test: `tests/test_roof_api.py`

**Interfaces:**
- Consumes: `teduh_agent.tools.roof.{analyze_roof_bytes, recommend_roof_action, MIN_CONFIDENCE}` (M6-T1); `PIL.Image`, `PIL.ImageOps`.
- Produces:
  - Di `routes.py`: `MAX_PHOTO_BYTES = 8 * 1024 * 1024`, `ALLOWED_PHOTO_TYPES`, `MAX_PHOTO_EDGE_PX = 2048`, `strip_metadata(data: bytes) -> tuple[bytes, str]`
  - `POST /api/roof` — `multipart/form-data` dengan field `photo`, opsional `kelurahan`

**Kenapa `pillow` pindah ke runtime:** `pipeline/strip_exif.py` sudah memakai Pillow tetapi hanya offline. Jalur unggahan **harus** menghapus metadata sebelum menyentuh disk, karena foto atap ber-GPS adalah alamat rumah (CLAUDE.md aturan 8). Itu berarti Pillow harus ada di image runtime.

- [ ] **Step 1: Pindahkan `pillow` di `pyproject.toml`**

Tambahkan ke `[project].dependencies`:

```toml
    "pillow>=10.3",
```

dan hapus dari grup `pipeline` (biarkan grup itu tetap punya sisanya). Lalu:

Run: `uv sync`

- [ ] **Step 2: Tulis tes yang gagal**

Buat `tests/test_roof_api.py`:

```python
"""The upload path. The metadata tests are the ones that matter: a geotagged roof photo is
a home address, so stripping must be structural (decode pixels, re-encode) rather than a
best-effort tag deletion that can miss a container."""

import io

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes import ALLOWED_PHOTO_TYPES, MAX_PHOTO_BYTES, router, strip_metadata

Image = pytest.importorskip("PIL.Image", reason="Pillow belum terpasang")


@pytest.fixture(scope="module")
def client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def _photo_with_gps(size=(800, 600)) -> bytes:
    """A JPEG carrying EXIF, including a GPS tag."""
    from PIL import Image as PILImage

    image = PILImage.new("RGB", size, (120, 90, 70))
    exif = image.getexif()
    exif[0x0110] = "TestCamera"  # Model
    exif[0x9003] = "2026:10:09 12:00:00"  # DateTimeOriginal
    exif[0x8825] = {1: "S", 2: ((6, 1), (10, 1), (0, 1))}  # GPSInfo
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", exif=exif)
    return buffer.getvalue()


@pytest.mark.unit
def test_strip_metadata_removes_every_exif_tag():
    from PIL import Image as PILImage

    cleaned, mime_type = strip_metadata(_photo_with_gps())
    assert mime_type == "image/jpeg"
    assert dict(PILImage.open(io.BytesIO(cleaned)).getexif()) == {}


@pytest.mark.unit
def test_strip_metadata_keeps_the_picture_itself():
    from PIL import Image as PILImage

    cleaned, _ = strip_metadata(_photo_with_gps(size=(800, 600)))
    assert PILImage.open(io.BytesIO(cleaned)).size == (800, 600)


@pytest.mark.unit
def test_strip_metadata_downscales_an_oversized_photo():
    from PIL import Image as PILImage

    from api.routes import MAX_PHOTO_EDGE_PX

    cleaned, _ = strip_metadata(_photo_with_gps(size=(4000, 3000)))
    assert max(PILImage.open(io.BytesIO(cleaned)).size) <= MAX_PHOTO_EDGE_PX


@pytest.mark.unit
def test_strip_metadata_rejects_something_that_is_not_an_image():
    with pytest.raises(ValueError, match="gambar"):
        strip_metadata(b"ini bukan gambar sama sekali")


@pytest.mark.integration
def test_endpoint_rejects_a_disallowed_content_type(client):
    response = client.post(
        "/api/roof", files={"photo": ("a.txt", b"halo", "text/plain")}
    )
    assert response.status_code == 415
    assert "image/jpeg" in response.json()["error"]


@pytest.mark.integration
def test_endpoint_rejects_an_oversized_upload(client):
    oversized = b"\xff\xd8\xff" + b"0" * (MAX_PHOTO_BYTES + 1)
    response = client.post(
        "/api/roof", files={"photo": ("big.jpg", oversized, "image/jpeg")}
    )
    assert response.status_code == 413


@pytest.mark.integration
def test_endpoint_rejects_a_corrupt_image(client):
    response = client.post(
        "/api/roof", files={"photo": ("a.jpg", b"bukan jpeg", "image/jpeg")}
    )
    assert response.status_code == 400


@pytest.mark.integration
def test_allowed_types_are_only_jpeg_and_png():
    assert ALLOWED_PHOTO_TYPES == {"image/jpeg", "image/png"}


@pytest.mark.integration
def test_endpoint_never_echoes_a_filesystem_path(client):
    response = client.post(
        "/api/roof", files={"photo": ("a.jpg", b"bukan jpeg", "image/jpeg")}
    )
    assert "/Users" not in response.text
    assert "/tmp" not in response.text


@pytest.mark.integration
def test_endpoint_rejects_a_location_finer_than_kelurahan(client):
    # CONCEPT §8.5: location is kelurahan-level at most.
    response = client.post(
        "/api/roof",
        files={"photo": ("a.jpg", _photo_with_gps(), "image/jpeg")},
        data={"kelurahan": "Jl. Mawar No. 12 RT 03 RW 05"},
    )
    assert response.status_code == 422
```

- [ ] **Step 3: Tulis endpoint di `api/routes.py`**

Tambahkan import:

```python
import io

from fastapi import File, Form, UploadFile

from teduh_agent.tools.roof import analyze_roof_bytes, recommend_roof_action
```

Tambahkan konstanta:

```python
# Phone photos routinely exceed this; anything larger is abuse or a mistake.
MAX_PHOTO_BYTES = 8 * 1024 * 1024

ALLOWED_PHOTO_TYPES = {"image/jpeg", "image/png"}

# Matches pipeline/strip_exif.py so the offline test set and the live path agree.
MAX_PHOTO_EDGE_PX = 2048

JPEG_QUALITY = 90

# A kelurahan name, nothing finer. Street, number, RT and RW are rejected outright.
ADDRESS_MARKERS = ("jl", "jalan", "no.", "rt", "rw", "gang", "gg.", "blok")
MAX_KELURAHAN_NAME_LEN = 60
```

Tambahkan fungsi dan route:

```python
def strip_metadata(data: bytes) -> tuple[bytes, str]:
    """Re-encode the pixels into a fresh container, discarding all metadata.

    This decodes and re-saves rather than deleting tags, because a geotagged roof photo is
    a home address (CLAUDE.md rule 8) and tag deletion can miss a container -- XMP, IPTC,
    a thumbnail with its own EXIF. Rebuilding the file means there is nothing to miss.
    Mirrors pipeline/strip_exif.py so the offline test set and the live path agree.
    """
    from PIL import Image, ImageOps

    try:
        image = Image.open(io.BytesIO(data))
        image.load()
    except Exception as error:  # noqa: BLE001 -- Pillow raises many unrelated types
        raise ValueError(f"berkas bukan gambar yang bisa dibaca: {error}") from error

    # Honour the orientation tag before dropping it, or portrait photos come out sideways.
    image = ImageOps.exif_transpose(image).convert("RGB")
    image.thumbnail((MAX_PHOTO_EDGE_PX, MAX_PHOTO_EDGE_PX))

    clean = Image.new("RGB", image.size)
    clean.putdata(list(image.getdata()))

    buffer = io.BytesIO()
    clean.save(buffer, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    return buffer.getvalue(), "image/jpeg"


def _looks_like_an_address(value: str) -> bool:
    lowered = f" {value.lower()} "
    return len(value) > MAX_KELURAHAN_NAME_LEN or any(
        f" {marker}" in lowered for marker in ADDRESS_MARKERS
    )


@router.post("/roof")
async def roof(photo: UploadFile = File(...), kelurahan: str | None = Form(None)) -> Any:
    """Classify an uploaded roof photo and return a rule-based recommendation.

    The photo is stripped of metadata in memory and never written to disk: the demo has no
    need to keep it, and not storing it is a stronger privacy guarantee than a lifecycle
    rule (docs/DECISIONS.md).
    """
    if photo.content_type not in ALLOWED_PHOTO_TYPES:
        return JSONResponse(
            status_code=415,
            content=fail(
                "Format foto harus image/jpeg atau image/png, "
                f"bukan {photo.content_type!r}."
            ),
        )

    raw = await photo.read()
    if len(raw) > MAX_PHOTO_BYTES:
        return JSONResponse(
            status_code=413,
            content=fail(
                f"Foto terlalu besar, maksimal {MAX_PHOTO_BYTES // (1024 * 1024)} MB."
            ),
        )

    if kelurahan and _looks_like_an_address(kelurahan):
        return JSONResponse(
            status_code=422,
            content=fail(
                "Lokasi hanya boleh sampai tingkat kelurahan. Jangan menuliskan nama "
                "jalan, nomor rumah, RT, atau RW."
            ),
        )

    try:
        cleaned, mime_type = strip_metadata(raw)
    except ValueError as error:
        return JSONResponse(status_code=400, content=fail(str(error)))

    try:
        analysed = analyze_roof_bytes(cleaned, mime_type)
    except Exception:  # noqa: BLE001 -- any genai/network failure
        return JSONResponse(
            status_code=502,
            content=fail("Analisis foto sedang tidak tersedia. Coba lagi sebentar lagi."),
        )

    advice = recommend_roof_action(analysed)
    if "error" in advice:
        return JSONResponse(status_code=400, content=fail(advice["error"]))

    return ok(
        {
            "roof": analysed,
            "recommendation": advice["recommendation"],
            "evidence": advice["evidence"],
            "guidance": advice["guidance"],
            "kelurahan": kelurahan or None,
            "facts": advice["facts"],
        }
    )
```

- [ ] **Step 4: Catat keputusan di `docs/DECISIONS.md`**

```markdown
## 2026-10-09 — Foto atap tidak disimpan sama sekali, bukan dihapus setelah 30 hari

- **Konsep (§8.5):** hapus EXIF sebelum disimpan, foto dihapus otomatis dari GCS setelah 30 hari (lifecycle rule).
- **Keputusan:** `POST /api/roof` menghapus metadata di memori, mengirim piksel ke Gemini, mengembalikan hasilnya, dan **tidak pernah menulis foto ke disk atau GCS**. `pillow` dipindahkan ke dependensi runtime agar penghapusan metadata bisa dilakukan di jalur permintaan.
- **Alasan:** demo tidak butuh foto itu lagi setelah dianalisis. Tidak menyimpan adalah jaminan privasi yang lebih kuat daripada aturan lifecycle, dan menghilangkan bucket, kredensial, serta aturan retensi yang harus dijelaskan ke juri. Penghapusan metadata dilakukan dengan membongkar piksel dan menulis ulang wadah baru, bukan menghapus tag, supaya tidak ada wadah metadata yang terlewat.
- **Risiko:** fitur P1 "peta laporan warga" butuh titik yang tersimpan. Kalau fitur itu dikerjakan, simpan **hanya** hasil klasifikasi dan `kelurahan`, tetap tanpa foto, dan catat di sini.
```

- [ ] **Step 5: Jalankan tes untuk memastikan lulus**

Run: `uv run pytest tests/test_roof_api.py -v`
Expected: PASS, 10 tes. Tes yang memanggil Gemini sungguhan tidak ada di sini — jalur itu diuji manual di Step 6 dan dievaluasi di M8.

- [ ] **Step 6: Uji dengan foto sungguhan**

Siapkan satu foto atap (tanpa wajah, nomor rumah, atau plat nomor), lalu:

```bash
uv run uvicorn api.main:app --port 8080 &
curl -s -X POST localhost:8080/api/roof -F "photo=@/path/ke/atap.jpg" \
  | python3 -m json.tool
```
Expected: delapan field terisi dengan nilai dari enum, rekomendasi yang masuk akal untuk atap itu, dan `confidence` yang jujur. Kalau fotonya kabur, `confidence` harus rendah dan rekomendasinya `retake_photo`.

Uji juga satu foto atap asbes kalau ada. `safety[0]` **wajib** berisi peringatan jangan diamplas.

- [ ] **Step 7: Verifikasi metadata benar-benar hilang**

```bash
uv run python -c "
import io
from PIL import Image
from api.routes import strip_metadata
raw = open('/path/ke/atap.jpg','rb').read()
before = dict(Image.open(io.BytesIO(raw)).getexif())
cleaned, _ = strip_metadata(raw)
after = dict(Image.open(io.BytesIO(cleaned)).getexif())
print('tag sebelum:', len(before), '| tag sesudah:', len(after))
assert after == {}, 'masih ada metadata'
print('ok, bersih')
"
```

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml uv.lock api/routes.py docs/DECISIONS.md tests/test_roof_api.py
git commit -m "feat: tambah endpoint unggah foto atap dengan penghapusan metadata struktural

Foto tidak pernah menyentuh disk, dan metadata dihapus dengan membongkar piksel
lalu menulis wadah baru, bukan menghapus tag satu per satu.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Definisi M6 selesai

- [ ] `ROOF_SCHEMA` punya delapan field dengan enum persis seperti CONCEPT §8.5 dan kosakata `labels.csv`.
- [ ] `recommend_roof_action` murni aturan, tanpa LLM.
- [ ] Atap asbes **selalu** mendapat peringatan jangan diamplas/dipotong/dibor sebagai baris keselamatan pertama, dan tidak pernah direkomendasikan cool roof atau green roof — termasuk ketika bentuknya datar.
- [ ] `confidence < 0,6` atau atap tidak terlihat → `retake_photo` beserta panduan sudut.
- [ ] `POST /api/roof` menolak tipe salah (415), ukuran berlebih (413), gambar rusak (400), dan lokasi yang lebih detail dari kelurahan (422).
- [ ] Metadata foto terbukti hilang setelah `strip_metadata`, dan foto tidak pernah ditulis ke disk.
- [ ] Sub-agen `roof_inspector` aktif di `build_all()`.
- [ ] `uv run pytest -q` hijau.
- [ ] **Belum boleh klaim akurasi** `roof_form` 85% / `material` 70% — itu butuh 30 foto berlabel, diukur di M8-T2.

**Selanjutnya:** [`m7a-web-foundation.md`](m7a-web-foundation.md) — fondasi frontend Next.js sesuai handoff desain, lalu [`m7b-web-features.md`](m7b-web-features.md).
