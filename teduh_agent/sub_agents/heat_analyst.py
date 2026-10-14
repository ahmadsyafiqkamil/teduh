"""Heat and vulnerability analysis."""

from google.adk.agents import LlmAgent

from teduh_agent.llm import resolve_model
from teduh_agent.prompts import instruction_for
from teduh_agent.tools.areas import (
    explain_drivers,
    find_area,
    get_area_profile,
    rank_priority_areas,
)

NAME = "heat_analyst"

DESCRIPTION = (
    "Menganalisis di mana panasnya, seberapa panas, siapa warga rentan yang terpapar, "
    "kelurahan mana yang perlu diprioritaskan, dan faktor apa yang membuat sebuah "
    "wilayah panas menurut model."
)


def build() -> LlmAgent:
    return LlmAgent(
        name=NAME,
        model=resolve_model(),
        description=DESCRIPTION,
        instruction=instruction_for("heat_analyst"),
        tools=[find_area, get_area_profile, rank_priority_areas, explain_drivers],
    )
