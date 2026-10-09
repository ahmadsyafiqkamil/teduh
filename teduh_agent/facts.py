"""Fact records: the only channel through which a number may reach the LLM.

CLAUDE.md rule 1 says Gemini never computes a figure, and rule 2 says every tool returns
`facts`. This module is the mechanism. A Fact binds a number to where it came from, and the
brief validator in teduh_agent/tools/brief.py rejects any figure in prose that has no
[[F:id]] marker pointing at one of these. That is the entire provenance guarantee, which is
why this module stays deliberately dumb: no rounding, no locale formatting, no domain logic.
Formatting belongs to the presentation layer, because a rounded number with a lost source is
exactly the failure this design exists to prevent.

The session ledger lives in ADK tool state so that get_session_facts() (M5) can hand the
policy_writer everything the conversation has already established.
"""

from typing import Any, TypedDict

Fact = TypedDict(
    "Fact",
    {"id": str, "label": str, "value": float | int | str, "unit": str, "source": str},
)

# Canonical source tokens. Anything else must go through source_evidence() or
# source_assumption() so the brief footnotes can resolve the citation.
SOURCE_DATA = "data:grid_features@v1"
SOURCE_MODEL = "model:lgbm@v1"

STATE_KEY = "facts"


def fact(id: str, label: str, value: float | int | str, unit: str, source: str) -> Fact:
    """Build one Fact.

    `id` must be stable across calls within a session: the policy brief references facts by
    id, so a drifting id silently breaks a citation rather than failing loudly.
    """
    if not id:
        raise ValueError("fact butuh id yang stabil, dapat kosong")
    if not source:
        raise ValueError(f"fact {id!r} butuh source (CLAUDE.md aturan 2), dapat kosong")
    return {"id": id, "label": label, "value": value, "unit": unit, "source": source}


def source_evidence(evidence_id: str) -> str:
    """Source token for a literature entry in data/evidence/interventions.json."""
    return f"evidence:{evidence_id}"


def source_assumption(key: str) -> str:
    """Source token for a config entry whose own `source` is "ASUMSI"."""
    return f"assumption:{key}"


def record(tool_context: Any, facts: list[Fact]) -> None:
    """Append facts to the session ledger, newest value winning on a duplicate id.

    A None context is a supported mode, not an error: api/routes.py calls the same tool
    functions over HTTP where there is no ADK session and therefore no ledger to keep.
    """
    if tool_context is None:
        return
    ledger: dict[str, Fact] = {f["id"]: f for f in tool_context.state.get(STATE_KEY, [])}
    ledger.update({f["id"]: f for f in facts})
    tool_context.state[STATE_KEY] = list(ledger.values())


def session_facts(tool_context: Any) -> list[Fact]:
    """Every fact recorded so far this session, as a copy the caller may not corrupt."""
    if tool_context is None:
        return []
    return list(tool_context.state.get(STATE_KEY, []))
