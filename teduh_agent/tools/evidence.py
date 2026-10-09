"""Published findings that put a model number in context (CONCEPT §7.7).

The comparable_to_model flag is the part that matters. interventions.json deliberately
records several metrics, and only lst_change_c is the same quantity the model predicts. A
cool roof study reporting an 11.58 C drop is measuring the ROOF SKIN; putting that beside an
area-average LST change of -0.8 C would be misleading even though both figures are real and
published. Flagging it lets the agent cite the study while saying plainly what it measured.

evidence_for() is the pure half, used by scenario_tools so a single scenario answer does not
record the same facts into the ledger twice. get_evidence() is the ADK wrapper that records.
"""

from google.adk.tools import ToolContext

from teduh_agent.facts import fact, record, source_evidence
from teduh_agent.store import get_store

# The only metric directly comparable to the model's output.
COMPARABLE_METRIC = "lst_change_c"


def evidence_for(intervention: str) -> dict:
    """Evidence entries for one intervention, comparable metrics first."""
    store = get_store()
    # Only verified entries surface to the agent: several data entries carry
    # verified=False with no url_or_doi and a note saying "do not quote until the primary
    # source is found". Presenting those as citable evidence would break the provenance
    # guarantee this product exists to uphold.
    matching = [
        entry
        for entry in store.evidence
        if entry["intervention"] == intervention and entry.get("verified")
    ]
    if not matching:
        known = sorted({entry["intervention"] for entry in store.evidence})
        return {
            "error": (
                f"Tidak ada entri bukti untuk {intervention!r}. "
                f"Yang tersedia: {', '.join(known)}."
            ),
            "evidence": [],
            "facts": [],
        }

    entries = [
        {**entry, "comparable_to_model": entry["metric"] == COMPARABLE_METRIC}
        for entry in matching
    ]
    entries.sort(key=lambda entry: not entry["comparable_to_model"])

    facts = []
    for entry in entries:
        for bound in ("min", "max"):
            facts.append(
                fact(
                    f"evidence.{entry['id']}.{bound}",
                    f"{entry['source_title']} ({entry['year']}), batas {bound}",
                    entry[f"value_{bound}"],
                    entry["unit"],
                    source_evidence(entry["id"]),
                )
            )

    return {
        "evidence": entries,
        "note": (
            "Hanya entri dengan comparable_to_model=true yang mengukur besaran yang sama "
            "dengan keluaran model (perubahan suhu permukaan per wilayah)."
        ),
        "facts": facts,
    }


def get_evidence(intervention: str, tool_context: ToolContext | None = None) -> dict:
    """Ambil temuan literatur untuk satu jenis intervensi pendinginan.

    Pakai tool ini setiap kali merekomendasikan intervensi, supaya angka model selalu
    disertai rentang dari studi yang sudah diterbitkan beserta sitasinya.

    Args:
        intervention: "tree_planting", "cool_roof", "green_roof", "cool_pavement",
            "green_curtain", atau "combined_package".

    Returns:
        dict dengan `evidence` (entri bersitasi, yang sebanding lebih dulu), `note`,
        dan `facts`.
    """
    result = evidence_for(intervention)
    record(tool_context, result["facts"])
    return result
