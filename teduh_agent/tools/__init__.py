"""Deterministic tools. This is the only path by which a number reaches Gemini.

Each tool is a thin wrapper over model/: it fetches, formats, and attaches provenance, but
performs no arithmetic of its own. If a tool needs a calculation that model/ does not
provide, the function belongs in model/, not here -- that boundary is what makes CLAUDE.md
rule 1 auditable.

Every tool takes an optional tool_context so api/routes.py can call the same function over
HTTP with no ADK session in play.
"""

from teduh_agent.tools.areas import (
    explain_drivers,
    find_area,
    get_area_profile,
    rank_priority_areas,
)
from teduh_agent.tools.evidence import get_evidence
from teduh_agent.tools.optimize import optimize_portfolio
from teduh_agent.tools.scenario_tools import simulate_intervention

# Tools available before M5 and M6 land. ALL_TOOLS appends the brief and roof tools when
# their modules exist, so the single-agent fallback works at every stage of the build.
CORE_TOOLS = [
    find_area,
    get_area_profile,
    rank_priority_areas,
    explain_drivers,
    simulate_intervention,
    optimize_portfolio,
    get_evidence,
]

ALL_TOOLS = list(CORE_TOOLS)

try:
    from teduh_agent.tools.brief import get_session_facts, render_policy_brief

    ALL_TOOLS += [get_session_facts, render_policy_brief]
except ImportError:  # M5 not built yet
    pass

try:
    from teduh_agent.tools.roof import analyze_roof_photo, recommend_roof_action

    ALL_TOOLS += [analyze_roof_photo, recommend_roof_action]
except ImportError:  # M6 not built yet
    pass
