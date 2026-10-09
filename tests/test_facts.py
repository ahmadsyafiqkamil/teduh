"""Facts are the provenance contract: if this file's rules bend, the brief validator in M5
has nothing solid to check against."""

import pytest

from teduh_agent.facts import (
    SOURCE_DATA,
    fact,
    record,
    session_facts,
    source_assumption,
    source_evidence,
)


class FakeToolContext:
    """Stands in for google.adk.tools.ToolContext, which only needs a mutable .state here."""

    def __init__(self) -> None:
        self.state: dict = {}


@pytest.mark.unit
def test_fact_carries_id_label_value_unit_and_source():
    # Arrange / Act
    result = fact("kel_ID3173040002.lst", "LST rata-rata", 44.61, "degC", SOURCE_DATA)

    # Assert
    assert result == {
        "id": "kel_ID3173040002.lst",
        "label": "LST rata-rata",
        "value": 44.61,
        "unit": "degC",
        "source": "data:grid_features@v1",
    }


@pytest.mark.unit
def test_fact_without_source_is_rejected():
    with pytest.raises(ValueError, match="source"):
        fact("kel_x.lst", "LST", 40.0, "degC", "")


@pytest.mark.unit
def test_fact_without_id_is_rejected():
    with pytest.raises(ValueError, match="id"):
        fact("", "LST", 40.0, "degC", SOURCE_DATA)


@pytest.mark.unit
def test_record_accumulates_facts_across_calls():
    # Arrange
    ctx = FakeToolContext()

    # Act
    record(ctx, [fact("a", "A", 1, "unit", SOURCE_DATA)])
    record(ctx, [fact("b", "B", 2, "unit", SOURCE_DATA)])

    # Assert
    assert {f["id"] for f in session_facts(ctx)} == {"a", "b"}


@pytest.mark.unit
def test_record_dedupes_by_id_keeping_the_newest_value():
    # Arrange
    ctx = FakeToolContext()

    # Act
    record(ctx, [fact("a", "A", 1, "unit", SOURCE_DATA)])
    record(ctx, [fact("a", "A", 99, "unit", SOURCE_DATA)])

    # Assert
    ledger = session_facts(ctx)
    assert len(ledger) == 1
    assert ledger[0]["value"] == 99


@pytest.mark.unit
def test_record_without_a_tool_context_is_a_supported_noop():
    # The REST API calls the same tool functions without an ADK session, so a missing
    # context must not raise -- there is simply no ledger to append to.
    record(None, [fact("a", "A", 1, "unit", SOURCE_DATA)])
    assert session_facts(None) == []


@pytest.mark.unit
def test_session_facts_returns_a_copy_so_callers_cannot_corrupt_the_ledger():
    # Arrange
    ctx = FakeToolContext()
    record(ctx, [fact("a", "A", 1, "unit", SOURCE_DATA)])

    # Act
    session_facts(ctx).clear()

    # Assert
    assert len(session_facts(ctx)) == 1


@pytest.mark.unit
def test_source_helpers_namespace_their_identifiers():
    assert source_evidence("ev_ndvi_kl_2025") == "evidence:ev_ndvi_kl_2025"
    assert source_assumption("cool_roof.albedo_cool") == "assumption:cool_roof.albedo_cool"
