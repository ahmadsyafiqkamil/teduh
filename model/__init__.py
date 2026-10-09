"""Deterministic computation layer: HVI, heat model, scenario engine, costs.

Nothing here knows about ADK or HTTP. The tools in teduh_agent/tools/ wrap these functions
and attach provenance; the REST API in api/ calls the same functions directly. That split is
what keeps CLAUDE.md rule 1 enforceable -- the LLM can only reach numbers through code that
lives in this package.
"""
