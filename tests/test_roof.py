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
def test_cited_evidence_is_always_verified():
    """interventions.json: verified=false must never be presented as evidence.

    teduh_agent/tools/evidence.py already enforces this. The roof path reads the same file
    and must not become the one place an unverified figure leaks out.
    """
    for roof in (
        _roof(roof_form="flat", material="concrete_slab"),
        _roof(material="metal_sheet"),
        _roof(material="asbestos_cement"),
        _roof(shade_from_trees="heavy"),
    ):
        result = recommend_roof_action(roof)
        assert all(entry["verified"] for entry in result["evidence"])


@pytest.mark.integration
def test_cited_evidence_names_what_it_measured():
    """A roof-skin figure of -11.58 C is not area cooling (interventions.json notes).

    Surfacing the number without its metric is how a 10x overstatement reaches a brief.
    """
    result = recommend_roof_action(_roof(roof_form="flat", material="concrete_slab"))
    assert all(entry["metric"] for entry in result["evidence"])
    assert all("comparable_to_model" in entry for entry in result["evidence"])
    assert any(
        entry["metric"] in fact["label"]
        for entry in result["evidence"]
        for fact in result["facts"]
    )


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
