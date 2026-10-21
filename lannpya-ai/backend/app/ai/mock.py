from app.ai.base import AddressProvider, ProviderInput, ProviderOutput
from app.schemas.orders import AddressFields


class MockAddressProvider(AddressProvider):
    @property
    def name(self) -> str:
        return "mock"

    async def parse(self, request: ProviderInput) -> ProviderOutput:
        # Deliberately independent of input; this is not an extraction algorithm.
        return ProviderOutput(address=AddressFields(), is_mock=True)
