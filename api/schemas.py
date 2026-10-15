"""HTTP request and response shapes.

This is the trust boundary. Every constraint the tools would otherwise have to re-check
lives here instead -- known intervention types, well-formed kel_id, a budget that is a real
number, a bounded number of kelurahan per request. Validating once at the edge is what lets
teduh_agent/tools/ assume well-formed input.

The list caps are not paranoia: each kelurahan in a simulate request means a model
prediction over its cells, so an unbounded list is a trivial way for one request to occupy
the whole Cloud Run instance.
"""

from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from model.scenario import INTERVENTION_TYPES, LEVELS

# BPS P-code: "ID" plus 10 digits, e.g. ID3173040002.
KEL_ID_PATTERN = r"^ID\d{10}$"

# The full DKI Jakarta dataset (264 kelurahan). A planner must be able to simulate a whole
# kota -- Jakarta Pusat alone has 44 -- so the old cap of 20 was a product bug, not a
# safeguard. The cap still exists to bound one request to the known dataset size: anything
# larger is either a mistake or abuse, and a single full-city pass (75 636 cells) stays well
# inside the Cloud Run timeout.
MAX_KELURAHAN_PER_REQUEST = 264
MAX_INTERVENTIONS_PER_REQUEST = len(INTERVENTION_TYPES)

# Rp 10 trillion. Far above any municipal programme; exists to reject typos and abuse.
MAX_BUDGET_IDR = 10**13


class ApiResponse[T](BaseModel):
    """Consistent envelope for every endpoint."""

    success: bool
    data: T | None = None
    error: str | None = None


def ok(data: Any) -> dict:
    return {"success": True, "data": data, "error": None}


def fail(message: str) -> dict:
    return {"success": False, "data": None, "error": message}


class InterventionInput(BaseModel):
    """One intervention, given either by named level or by explicit parameters."""

    type: str
    level: str | None = None
    params: dict[str, float] | None = None

    @field_validator("type")
    @classmethod
    def _known_type(cls, value: str) -> str:
        if value not in INTERVENTION_TYPES:
            raise ValueError(
                f"jenis intervensi tidak dikenal: {value}. "
                f"Pilihan: {', '.join(INTERVENTION_TYPES)}"
            )
        return value

    @model_validator(mode="after")
    def _level_or_params(self) -> "InterventionInput":
        if self.level is None and not self.params:
            raise ValueError("intervensi butuh level atau params")
        if self.level is not None and self.level not in LEVELS[self.type]:
            raise ValueError(
                f"level tidak dikenal untuk {self.type}: {self.level}. "
                f"Pilihan: {', '.join(LEVELS[self.type])}"
            )
        return self


def _well_formed_ids(value: list[str]) -> list[str]:
    """Every kel_id must match the BPS P-code shape (shared by simulate and optimize)."""
    import re

    for kel_id in value:
        if not re.match(KEL_ID_PATTERN, kel_id):
            raise ValueError(f"kel_id tidak valid: {kel_id}")
    return value


class SimulateRequest(BaseModel):
    """Slider-driven scenario, no LLM involved."""

    kel_ids: list[str] = Field(min_length=1, max_length=MAX_KELURAHAN_PER_REQUEST)
    interventions: list[InterventionInput] = Field(
        min_length=1, max_length=MAX_INTERVENTIONS_PER_REQUEST
    )

    @field_validator("kel_ids")
    @classmethod
    def _validate_kel_ids(cls, value: list[str]) -> list[str]:
        return _well_formed_ids(value)


class OptimizeRequest(BaseModel):
    """Form-driven portfolio, no LLM involved.

    `scope` ("all", kota/kecamatan/kelurahan) and `kel_ids` are alternative ways to bound the
    portfolio. `kel_ids` wins when both are supplied: the slider dock sends an explicit list
    of picked kelurahan, while the chat path keeps using `scope`.
    """

    scope: str = "all"
    kel_ids: list[str] | None = Field(default=None, max_length=MAX_KELURAHAN_PER_REQUEST)
    budget_idr: int = Field(gt=0, le=MAX_BUDGET_IDR)
    equity_share: float | None = Field(default=None, ge=0.0, le=1.0)
    allowed: list[str] | None = Field(default=None, max_length=MAX_INTERVENTIONS_PER_REQUEST)

    @field_validator("kel_ids")
    @classmethod
    def _validate_kel_ids(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        return _well_formed_ids(value)

    @field_validator("allowed")
    @classmethod
    def _known_types(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        unknown = [item for item in value if item not in INTERVENTION_TYPES]
        if unknown:
            raise ValueError(f"jenis intervensi tidak dikenal: {', '.join(unknown)}")
        return value
