"""Config and data-quality conventions shared by model/ and teduh_agent/.

These two helpers used to live in teduh_agent/store.py, and that created an import cycle
which broke three of the documented commands. teduh_agent/__init__.py must do
`from . import agent` for ADK discovery, which eagerly pulls teduh_agent.tools, which
imports model.scenario and model.train. So any module in model/ that reached back into
teduh_agent.store triggered the agent graph mid-import and crashed:

    uvicorn api.main:app   -> ImportError: partially initialized module model.scenario
    python -m model.train  -> ImportError: partially initialized module model.train

The suite never caught it because conftest imports teduh_agent first, which happens to warm
the graph in a working order. The entry point decides import order, not the tests.

The fix is the dependency direction: model/ is the leaf and must not know teduh_agent
exists. teduh_agent.store re-exports both names, so existing call sites are unchanged.

Note: "config" here means the config/*.yaml constants, not a settings object.
"""

from typing import Any

import pandas as pd

GOOD_QUALITY = "good"


def good_cells(grid: pd.DataFrame) -> pd.DataFrame:
    """Cells with enough clean observations to trust thermally (DECISIONS 2026-10-09).

    Low-quality cells stay on the map and keep their residents, but they are excluded from
    every thermal statistic and from model training.
    """
    return grid[grid["lst_quality"] == GOOD_QUALITY]


def config_entry(cfg: dict, *path: str) -> tuple[Any, str]:
    """Read one config constant as (value, source).

    Enforces CLAUDE.md rule 4 at read time: an entry without a `source` raises instead of
    quietly becoming an unattributed number in a policy brief.
    """
    node: Any = cfg
    for key in path:
        if not isinstance(node, dict) or key not in node:
            raise KeyError(f"config path {'.'.join(path)} tidak ada")
        node = node[key]
    if not isinstance(node, dict) or "value" not in node:
        raise KeyError(f"config entry {'.'.join(path)} tidak punya value")
    if "source" not in node:
        raise KeyError(f"config entry {'.'.join(path)} tidak punya source (CLAUDE.md aturan 4)")
    return node["value"], node["source"]
