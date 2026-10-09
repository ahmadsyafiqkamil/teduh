"""Manual evaluation runners, deliberately outside the pytest suite.

These scripts call Gemini for real, so importing them at collection time would make
`uv run pytest` slow, costly, and non-deterministic. They are run by hand:

    uv run python -m tests.eval.run_golden
    uv run python -m tests.eval.eval_roof
"""
