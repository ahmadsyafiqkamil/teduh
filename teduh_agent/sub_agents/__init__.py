"""The four specialists the coordinator routes to (CONCEPT §8.1).

Tool sets do not overlap, and that is load-bearing. If heat_analyst could also reach
optimize_portfolio, the coordinator's routing decision would become cosmetic and the
expected_agent assertions in tests/eval/golden_questions.yaml would stop meaning anything.

policy_writer and roof_inspector are skipped while their tools (M5, M6) do not exist yet, so
the agent can be run and demoed at every stage of the build rather than only at the end.
"""

from google.adk.agents import LlmAgent

from teduh_agent.llm import model_name

MODEL = model_name()


def build_all() -> list[LlmAgent]:
    """Every sub-agent whose tools are present."""
    from teduh_agent.sub_agents import heat_analyst, intervention_planner

    agents = [heat_analyst.build(), intervention_planner.build()]

    try:
        from teduh_agent.sub_agents import policy_writer

        agents.append(policy_writer.build())
    except ImportError:  # M5 not built yet
        pass

    try:
        from teduh_agent.sub_agents import roof_inspector

        agents.append(roof_inspector.build())
    except ImportError:  # M6 not built yet
        pass

    return agents
