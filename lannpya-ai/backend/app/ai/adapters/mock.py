from app.ai.extraction import (
    AddressExtractionProvider,
    AIExtractionResponse,
    ExtractionUnavailableError,
    SanitizedAddressInput,
)


class MockExtractionProvider(AddressExtractionProvider):
    is_external = False
    is_mock = True

    @property
    def name(self) -> str:
        return "mock"

    async def extract(self, payload: SanitizedAddressInput, *, timeout_seconds: float) -> str:
        # No made-up sample landmark, customer, or instructions. AI values unavailable.
        return AIExtractionResponse().model_dump_json()


class DisabledExtractionProvider(AddressExtractionProvider):
    is_external = False

    @property
    def name(self) -> str:
        return "disabled"

    async def extract(self, payload: SanitizedAddressInput, *, timeout_seconds: float) -> str:
        raise ExtractionUnavailableError("AI assistance is disabled")
