"""Policy brief writing with number provenance markers."""

from google.adk.agents import LlmAgent

from teduh_agent.llm import resolve_model
from teduh_agent.prompts import compose
from teduh_agent.tools.brief import get_session_facts, render_policy_brief

NAME = "policy_writer"

DESCRIPTION = (
    "Menulis draf policy brief terstruktur untuk Bappeda dan dinas teknis, dengan "
    "setiap angka ditandai agar bisa ditelusuri ke sumbernya, lalu merendernya ke PDF."
)


def build() -> LlmAgent:
    return LlmAgent(
        name=NAME,
        model=resolve_model(),
        description=DESCRIPTION,
        instruction=compose("policy_writer"),
        tools=[get_session_facts, render_policy_brief],
    )
