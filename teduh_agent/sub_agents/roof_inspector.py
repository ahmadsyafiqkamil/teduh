"""Citizen-facing roof check."""

from google.adk.agents import LlmAgent

from teduh_agent.llm import resolve_model
from teduh_agent.prompts import instruction_for
from teduh_agent.tools.roof import analyze_roof_photo, recommend_roof_action

NAME = "roof_inspector"

DESCRIPTION = (
    "Membantu warga memeriksa foto atap rumahnya, mengenali bentuk dan materialnya, "
    "lalu memberi rekomendasi cool roof atau green roof beserta catatan keselamatan."
)


def build() -> LlmAgent:
    return LlmAgent(
        name=NAME,
        model=resolve_model(),
        description=DESCRIPTION,
        instruction=instruction_for("roof_inspector"),
        tools=[analyze_roof_photo, recommend_roof_action],
    )
