"""Heat and vulnerability analysis."""

import os

from google.adk.agents import LlmAgent

from teduh_agent.prompts import compose
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
        model=os.environ.get("TEDUH_MODEL", "gemini-3.8-flash"),
        description=DESCRIPTION,
        instruction=compose("heat_analyst"),
        tools=[find_area, get_area_profile, rank_priority_areas, explain_drivers],
    )
