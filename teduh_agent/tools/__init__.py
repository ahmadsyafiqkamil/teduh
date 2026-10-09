"""Deterministic tools. This is the only path by which a number reaches Gemini.

Each tool is a thin wrapper over model/: it fetches, formats, and attaches provenance, but
performs no arithmetic of its own. If a tool needs a calculation that model/ does not
provide, the function belongs in model/, not here -- that boundary is what makes CLAUDE.md
rule 1 auditable.

Every tool takes an optional tool_context so api/routes.py can call the same function over
HTTP with no ADK session in play.
"""
