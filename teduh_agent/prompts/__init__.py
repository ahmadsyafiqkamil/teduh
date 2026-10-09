"""System instructions, kept as .md files rather than Python strings.

Two reasons. Long Indonesian prose inside a .py file drowns the code, and these instructions
are the single most-edited thing during golden-question tuning -- editing a .md touches no
logic at all, so a prompt change cannot break an import.

shared_rules.md is prepended to every agent prompt by compose(). That is what stops the
"never invent a number" rule from being present in three sub-agents and quietly missing from
the fourth.
"""

from functools import lru_cache
from pathlib import Path

PROMPT_DIR = Path(__file__).resolve().parent
SHARED = "shared_rules"


@lru_cache(maxsize=16)
def load(name: str) -> str:
    """Read one prompt file by stem."""
    path = PROMPT_DIR / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"prompt {name!r} tidak ada di {PROMPT_DIR}")
    return path.read_text(encoding="utf-8")


def compose(name: str) -> str:
    """Shared rules first, then the agent's own instruction."""
    return f"{load(SHARED).strip()}\n\n{load(name).strip()}\n"


def available() -> list[str]:
    return sorted(path.stem for path in PROMPT_DIR.glob("*.md"))
