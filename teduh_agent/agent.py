"""ADK entry point: the coordinator, plus the single-agent escape hatch.

In multi-agent mode the coordinator holds NO analysis tools of its own. That is deliberate:
a coordinator that can answer directly will sometimes do so, which skips the specialist
prompt that carries the metric caveats, and the first sign of trouble is a confident answer
with no "suhu permukaan" qualifier anywhere in it.

TEDUH_SINGLE_AGENT=1 collapses everything into one LlmAgent holding every tool. CONCEPT §12
makes this a day-6 decision point, and the tool contract is identical either way, so the
switch costs nothing but a restart.
"""

import os

from google.adk.agents import LlmAgent

from teduh_agent.llm import resolve_model
from teduh_agent.prompts import compose, instruction_for
from teduh_agent.sub_agents import build_all
from teduh_agent.tools import ALL_TOOLS

MODEL = resolve_model()

SINGLE_AGENT_ENV = "TEDUH_SINGLE_AGENT"

NAME = "teduh_coordinator"

DESCRIPTION = (
    "Koordinator TEDUH untuk perencanaan mitigasi panas perkotaan tingkat kelurahan "
    "di DKI Jakarta."
)


def is_single_agent() -> bool:
    """True when the multi-agent routing fallback is active."""
    return os.environ.get(SINGLE_AGENT_ENV, "0").strip().lower() in {"1", "true", "yes"}


def build_root() -> LlmAgent:
    """The coordinator, in whichever mode the environment asks for."""
    if is_single_agent():
        return LlmAgent(
            name=NAME,
            model=MODEL,
            description=DESCRIPTION,
            # Every specialist instruction folded into one, so no caveat is lost when the
            # sub-agents are not there to carry it. The dynamic provider appends the active
            # language directive, exactly as the multi-agent path does.
            instruction=instruction_for(
                "single_agent",
                base="\n\n".join(
                    compose(name)
                    for name in (
                        "heat_analyst",
                        "intervention_planner",
                        "policy_writer",
                        "roof_inspector",
                    )
                ),
            ),
            tools=ALL_TOOLS,
        )

    return LlmAgent(
        name=NAME,
        model=MODEL,
        description=DESCRIPTION,
        instruction=instruction_for("coordinator"),
        sub_agents=build_all(),
    )


root_agent = build_root()
