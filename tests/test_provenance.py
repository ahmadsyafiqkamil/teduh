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
