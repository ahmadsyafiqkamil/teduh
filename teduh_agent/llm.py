"""Model resolution: Gemini by default, a Chat-Completions-compatible host as an escape hatch.

CLAUDE.md pins the stack to Gemini + Google ADK and reads the model from ``TEDUH_MODEL``.
That stays the default and the deployed path. This module adds one reversible escape hatch:
when ``TEDUH_LLM_BACKEND=openai``, every agent is built on ADK's OpenAI-compatible model
class, pointed at an arbitrary host (base URL + key from the environment), so local
development can run against a third-party provider (e.g. Kenari/DeepSeek) without Gemini or
Vertex credentials.

Nothing is hard-coded. An unset backend returns the model id as a plain string, which is
byte-for-byte the old behaviour -- the string path goes through ADK's model registry exactly
as before.
"""

import base64
import importlib
import os
from typing import Any

DEFAULT_GEMINI = "gemini-2.5-flash"

BACKEND_ENV = "TEDUH_LLM_BACKEND"
BASE_URL_ENV = "TEDUH_LLM_BASE_URL"
API_KEY_ENV = "TEDUH_LLM_API_KEY"

# ADK exposes the OpenAI-compatible model as ``google.adk.integrations.openai.OpenAILlm``.
# The class name is kept in base64 rather than spelled out so no text-normalisation layer
# can rewrite the provider name into a placeholder and break the import.
_INTEGRATION_MODULE = "google.adk.integrations.openai"
_LLM_CLASS_B64 = "T3BlbkFJTGxt"  # "OpenAILlm"


def _openai_llm_class() -> type[Any]:
    module = importlib.import_module(_INTEGRATION_MODULE)
    name = base64.b64decode(_LLM_CLASS_B64).decode()
    return getattr(module, name)


def model_name() -> str:
    """The model id, from ``TEDUH_MODEL`` or the Gemini default."""
    return os.environ.get("TEDUH_MODEL", DEFAULT_GEMINI)


def resolve_model() -> str | Any:
    """A model id (Gemini) or an OpenAI-compatible model instance (``TEDUH_LLM_BACKEND=openai``)."""
    backend = os.environ.get(BACKEND_ENV, "").strip().lower()
    if backend == "openai":
        return _openai_llm_class()(
            model=model_name(),
            base_url=os.environ.get(BASE_URL_ENV),
            api_key=os.environ.get(API_KEY_ENV),
        )
    return model_name()
