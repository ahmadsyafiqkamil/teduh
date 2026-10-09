"""Citizen-facing roof check."""

import os

from google.adk.agents import LlmAgent

from teduh_agent.prompts import compose
from teduh_agent.tools.roof import analyze_roof_photo, recommend_roof_action

NAME = "roof_inspector"

DESCRIPTION = (
    "Membantu warga memeriksa foto atap rumahnya, mengenali bentuk dan materialnya, "
    "lalu memberi rekomendasi cool roof atau green roof beserta catatan keselamatan."
)


def build() -> LlmAgent:
    return LlmAgent(
        name=NAME,
        model=os.environ.get("TEDUH_MODEL", "gemini-3.8-flash"),
        description=DESCRIPTION,
        instruction=compose("roof_inspector"),
        tools=[analyze_roof_photo, recommend_roof_action],
    )
