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
from typing import Any, Callable

PROMPT_DIR = Path(__file__).resolve().parent
SHARED = "shared_rules"

# Session-state key the web frontend writes to tell the agent which language to answer in.
# Default "id" when absent, so an old client or a bare tool call stays Bahasa Indonesia.
LANG_STATE_KEY = "lang"

InstructionProvider = Callable[[Any], str]


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


def language_directive(lang: str) -> str:
    """The one line that overrides the shared-rules default when the UI toggles English.

    shared_rules.md says "Jawab dalam Bahasa Indonesia ... kecuali pengguna memakai bahasa
    lain lebih dulu." This directive is the machine-readable version of that escape: the
    web writes `lang` into session state, and every agent reads it here. Because the rule
    lives in ONE place, the no-invented-numbers and surface-temperature caveats cannot
    diverge between languages.
    """
    if (lang or "id").strip().lower() == "en":
        return (
            "Bahasa aktif sesi ini adalah Inggris (dipilih pengguna lewat toggle UI). "
            "Jawab dalam Bahasa Inggris yang jelas, pakai format angka gaya Inggris "
            "(titik desimal, koma ribuan, 'of' untuk peringkat). Tetap patuhi semua aturan "
            "TEDUH di atas: angka hanya dari tool, sebutkan suhu permukaan, dan jangan "
            "mengarang harga."
        )
    return (
        "Bahasa aktif sesi ini adalah Bahasa Indonesia. Jawab dalam Bahasa Indonesia yang "
        "jelas untuk pegawai pemerintah daerah, pakai format angka gaya Indonesia (koma "
        "desimal, titik ribuan)."
    )


def _lang_from(ctx: Any) -> str:
    """Read the session language, defaulting to Indonesian."""
    try:
        state = ctx.state if ctx is not None else {}
        value = state.get(LANG_STATE_KEY) if state else None
    except Exception:  # noqa: BLE001 -- any context without .state is treated as default
        value = None
    return value or "id"


def instruction_for(name: str, base: str | None = None) -> InstructionProvider:
    """A dynamic instruction provider that appends the active-language directive.

    ADK resolves this by calling it with the request context, so the agent answers in
    whatever language the frontend wrote into session state via state_delta. When there is
    no context (single-agent smoke tests, direct tool use) it falls back to Indonesian,
    byte-for-byte the old behaviour.

    `base` overrides the composed prompt; the single-agent fallback passes its own folded
    instructions instead of a single prompt file.
    """
    body = base if base is not None else compose(name)

    def _provider(ctx: Any) -> str:
        return f"{body}\n\n{language_directive(_lang_from(ctx))}"

    return _provider


def available() -> list[str]:
    return sorted(path.stem for path in PROMPT_DIR.glob("*.md"))
