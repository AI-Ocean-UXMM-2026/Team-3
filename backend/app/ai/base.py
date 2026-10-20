from abc import ABC, abstractmethod

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.orders import AddressFields


class ProviderInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)
    raw_text: str = Field(min_length=1, max_length=10000)


class ProviderOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    address: AddressFields
    is_mock: bool


class AIProviderError(Exception):
    """Provider unavailable or invalid response. Never expose upstream details to clients."""


class AddressProvider(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Public provider identifier; never a credential or model secret."""

    @abstractmethod
    async def parse(self, request: ProviderInput) -> ProviderOutput:
        """Return validated fields or raise AIProviderError; never assign confidence."""
