"""ADK entry point.

M0 ships exactly one tool so the whole deployment path -- uv sync, adk web, Docker image,
Cloud Run -- is proven before any domain logic lands. M4 replaces this single agent with
teduh_coordinator plus four sub-agents; the tool contract does not change, which is what
makes deferring that swap safe.

Tool docstrings are written in Indonesian on purpose: ADK feeds them to Gemini as the tool
description, and users ask in Indonesian, so Indonesian descriptions match more reliably.
Code comments and identifiers stay English per CLAUDE.md rule 7.
"""

import os

from google.adk.agents import LlmAgent
from google.adk.tools import ToolContext

from .facts import SOURCE_DATA, fact, record
from .store import get_store

# Never hard-code a model id: the Gemini Flash generation moves, and CONCEPT §11.1 requires
# this to be swappable without a code change.
MODEL = os.environ.get("TEDUH_MODEL", "gemini-3.8-flash")

INSTRUCTION = """\
Kamu adalah TEDUH, asisten perencanaan mitigasi panas perkotaan untuk pemerintah daerah
di Indonesia.

Aturan yang tidak boleh dilanggar:
- Jawab dalam Bahasa Indonesia yang jelas untuk pegawai pemerintah daerah, kecuali
  pengguna memakai bahasa lain.
- JANGAN PERNAH menulis angka yang tidak berasal dari hasil tool. Kalau datanya tidak ada,
  katakan tidak ada.
- Sebut sumber angka ketika relevan.
"""


def count_kelurahan(tool_context: ToolContext) -> dict:
    """Hitung jumlah kelurahan yang tersedia dalam data TEDUH.

    Gunakan tool ini kalau pengguna bertanya berapa banyak kelurahan yang dicakup TEDUH
    atau seberapa luas cakupan datanya.

    Returns:
        dict dengan kunci `facts`: daftar fakta berisi jumlah kelurahan beserta sumbernya.
    """
    store = get_store()
    facts = [
        fact(
            "data.kelurahan_count",
            "Jumlah kelurahan dalam data TEDUH",
            len(store.kelurahan),
            "kelurahan",
            SOURCE_DATA,
        )
    ]
    record(tool_context, facts)
    return {"facts": facts}


root_agent = LlmAgent(
    name="teduh_coordinator",
    model=MODEL,
    description="Koordinator TEDUH untuk analisis panas perkotaan tingkat kelurahan.",
    instruction=INSTRUCTION,
    tools=[count_kelurahan],
)
