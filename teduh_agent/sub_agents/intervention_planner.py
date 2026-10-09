"""Scenario simulation and budget portfolio."""

import os

from google.adk.agents import LlmAgent

from teduh_agent.prompts import compose
from teduh_agent.tools.evidence import get_evidence
from teduh_agent.tools.optimize import optimize_portfolio
from teduh_agent.tools.scenario_tools import simulate_intervention

NAME = "intervention_planner"

DESCRIPTION = (
    "Menyimulasikan dampak intervensi pendinginan (pohon, cool roof, green roof), "
    "menyusun portofolio paket dalam batas anggaran dengan kendala keadilan, dan "
    "menyertakan rentang temuan dari literatur."
)


def build() -> LlmAgent:
    return LlmAgent(
        name=NAME,
        model=os.environ.get("TEDUH_MODEL", "gemini-3.8-flash"),
        description=DESCRIPTION,
        instruction=compose("intervention_planner"),
        tools=[simulate_intervention, optimize_portfolio, get_evidence],
    )
