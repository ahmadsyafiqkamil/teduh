"""Cek Atap: Gemini describes the roof, rules decide what to do about it (CONCEPT §8.5).

That split is the design, not an implementation detail. analyze_roof_photo returns a
description and never recommends anything; recommend_roof_action is pure Python with no LLM
anywhere in it. The reason is the asbestos warning: a homeowner sanding an asbestos-cement
sheet releases fibres, and that warning must fire on every single asbestos photo. A rule
engine guarantees that. A language model, however well prompted, does not.

The rules are ordered so asbestos is checked before anything else. Flat asbestos sheeting
would otherwise match the green-roof branch and be told to add soil and plants to the one
material that must not be drilled into.

Evidence is filtered to verified=true and carries its `metric`, matching
teduh_agent/tools/evidence.py. Both matter here: the two entries backing roof advice measure
ROOF SKIN temperature (-11.58 and -13.14 degC), roughly ten times any neighbourhood LST
effect, so a figure shown without naming what it measured is a 10x overstatement waiting to
reach a brief.
"""

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

from google.adk.tools import ToolContext

from teduh_agent.facts import SOURCE_MODEL, Fact, fact, record, source_evidence
from teduh_agent.store import get_store
from teduh_agent.tools.evidence import COMPARABLE_METRIC

MODEL = os.environ.get("TEDUH_MODEL", "gemini-2.5-flash")

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

# Evidence entries backing each action (data/evidence/interventions.json). Ids are listed
# per action and filtered for verified=true at read time, so an entry that gets verified
# later starts appearing without this table being touched.
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


def _cited_evidence(evidence_ids: tuple[str, ...]) -> list[dict]:
    """Verified entries only, each flagged with whether it measures the model's quantity.

    Mirrors evidence_for() in teduh_agent/tools/evidence.py. verified=false entries have no
    url_or_doi and a note saying not to quote them, so surfacing one here would break the
    provenance guarantee the product rests on.
    """
    store = get_store()
    return [
        {**entry, "comparable_to_model": entry["metric"] == COMPARABLE_METRIC}
        for entry in store.evidence
        if entry["id"] in evidence_ids and entry.get("verified")
    ]


def _evidence_facts(evidence: list[dict]) -> list[Fact]:
    """One fact per cited entry, with the metric in the label.

    The metric is in the label on purpose: ev_coolroof_id_surface reports -11.58 degC of
    ROOF SKIN cooling, and a reader who takes that for area cooling overstates what TEDUH
    delivers by roughly tenfold.
    """
    return [
        fact(
            f"roof.evidence.{entry['id']}.min",
            f"{entry['source_title']} ({entry['year']}), {entry['metric']}, batas bawah",
            entry["value_min"],
            entry["unit"],
            source_evidence(entry["id"]),
        )
        for entry in evidence
    ]


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
    path = Path(image_uri)
    if not path.exists():
        return {
            "error": (
                f"Foto {image_uri!r} tidak bisa dibaca. Unggah foto lewat halaman "
                "Cek Atap lebih dulu."
            ),
            "facts": [],
        }

    mime_type = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
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
    evidence = _cited_evidence(decision.evidence_ids)
    facts = _evidence_facts(evidence)
    record(tool_context, facts)

    return {
        "recommendation": asdict(decision)
        | {"safety": list(decision.safety), "evidence_ids": list(decision.evidence_ids)},
        "evidence": evidence,
        "guidance": RETAKE_GUIDANCE if decision.action == "retake_photo" else "",
        "facts": facts,
    }
