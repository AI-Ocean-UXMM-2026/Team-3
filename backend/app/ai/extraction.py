"""Provider-neutral enrichment contract; separate from the Phase 1 demo interface."""

from abc import ABC, abstractmethod
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.ai.base import AIProviderError

EnrichmentField = Literal["landmark", "building_floor_unit", "delivery_instructions"]


class SanitizedFragment(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    id: str = Field(pattern=r"^fragment_[0-9]+$")
    text: str = Field(min_length=1, max_length=512)


class SanitizedAddressInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    township: str | None = Field(default=None, max_length=64)
    fragments: tuple[SanitizedFragment, ...] = Field(min_length=1, max_length=8)
    requested_fields: tuple[EnrichmentField, ...] = Field(min_length=1, max_length=3)


class AIFieldSuggestion(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    value: str = Field(min_length=1, max_length=500)
    fragment_id: str = Field(pattern=r"^fragment_[0-9]+$")
    quote: str = Field(min_length=1, max_length=512)

    @field_validator("value", "quote")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Suggestion and quote must contain text")
        return value


class AIExtractionResponse(BaseModel):
    """No phone, COD, customer name, township, street, coordinates, or confidence fields."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    landmark: AIFieldSuggestion | None = None
    building_floor_unit: AIFieldSuggestion | None = None
    delivery_instructions: AIFieldSuggestion | None = None


class AddressExtractionProvider(ABC):
    # External adapters are blocked in Phase 3 even if injected by server code.
    is_external: bool = True
    is_mock: bool = False

    @property
    @abstractmethod
    def name(self) -> str:
        """A public, non-sensitive identifier, not a model key or URL."""

    @abstractmethod
    async def extract(self, payload: SanitizedAddressInput, *, timeout_seconds: float) -> str:
        """Return JSON matching AIExtractionResponse; use async/cancellable transport.

        SDK/HTTP details belong in an adapter. Enforce timeout_seconds at transport
        level too. Treat input fragments as untrusted data, never system instructions.
        Map upstream failures to the typed exceptions below without logging payloads.
        """


class ExtractionUnavailableError(AIProviderError):
    pass


class ExtractionTimeoutError(AIProviderError):
    pass


class ExtractionRateLimitError(AIProviderError):
    def __init__(self, retry_after_seconds: int | None = None):
        super().__init__("AI rate limit reached")
        self.retry_after_seconds = (
            min(max(retry_after_seconds, 1), 86400) if type(retry_after_seconds) is int else None
        )
