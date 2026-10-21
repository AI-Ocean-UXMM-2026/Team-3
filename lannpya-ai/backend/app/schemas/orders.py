from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ParseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    raw_text: str = Field(min_length=1, max_length=10000)

    @field_validator("raw_text")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Text must contain non-whitespace characters")
        return value


class AddressFields(BaseModel):
    """Missing information stays null; no inferred coordinates are represented."""

    model_config = ConfigDict(extra="forbid", strict=True)
    customer_name: str | None = None
    phone_number: str | None = None
    township: str | None = None
    street: str | None = None
    landmark: str | None = None
    building_floor_unit: str | None = None
    cod_amount: int | None = Field(default=None, ge=0, description="Whole Myanmar kyat (MMK)")
    delivery_instructions: str | None = None
    time_window: str | None = None


class Confidence(StrEnum):
    GREEN = "GREEN"
    AMBER = "AMBER"
    RED = "RED"


class ValidationReason(BaseModel):
    code: str
    message: str


class ExtractionEvidence(BaseModel):
    """Offsets are Python character offsets into normalized_text, end exclusive."""

    value: str | int | None
    matched_text: str
    start: int = Field(ge=0)
    end: int = Field(ge=0)


class FieldSource(BaseModel):
    method: Literal["rule", "dictionary", "not_extracted", "ai"] = "not_extracted"
    status: Literal["extracted", "missing", "ambiguous", "invalid"] = "missing"
    rule: str | None = None
    evidence: list[ExtractionEvidence] = Field(default_factory=list)
    verified: bool = False
    dataset: str | None = None
    provider: str | None = None
    requires_review: bool = False
    ai_suggestion: str | None = None


class NormalizationInfo(BaseModel):
    encoding: Literal["unicode_or_undetermined", "zawgyi", "ambiguous", "non_myanmar"]
    zawgyi_converted: bool = False
    digits_normalized: bool = False
    warnings: list[ValidationReason] = Field(default_factory=list)


class LocationVerification(BaseModel):
    status: Literal["unverified", "verified"] = "unverified"
    dataset: str | None = None
    source_url: str | None = None


class AIAvailability(BaseModel):
    status: Literal[
        "not_requested",
        "mock",
        "disabled",
        "available",
        "timeout",
        "rate_limited",
        "invalid_response",
        "unavailable",
        "privacy_blocked",
    ] = "not_requested"
    provider: str | None = None
    is_mock: bool = False
    attempted: bool = False
    message: str = "AI assistance was not requested."
    retry_after_seconds: int | None = Field(default=None, ge=1, le=86400)
    applied_fields: list[str] = Field(default_factory=list)
    suggested_fields: list[str] = Field(default_factory=list)


class ParseResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    is_mock: bool
    provider: str
    notice: str
    address: AddressFields
    confidence: Confidence
    validation_reasons: list[ValidationReason] = Field(min_length=1)
    # Additive fields; legacy mock responses remain valid and keep their old semantics.
    original_text: str | None = None
    normalized_text: str | None = None
    normalization: NormalizationInfo | None = None
    field_sources: dict[str, FieldSource] = Field(default_factory=dict)
    location_verification: LocationVerification = Field(default_factory=LocationVerification)
    ai: AIAvailability = Field(default_factory=AIAvailability)
    manual_review_required: bool = True


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: Literal["LannPya AI"] = "LannPya AI"
