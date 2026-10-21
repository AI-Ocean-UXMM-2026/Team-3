from app.ai.adapters.mock import DisabledExtractionProvider, MockExtractionProvider
from app.ai.base import AddressProvider
from app.ai.extraction import AddressExtractionProvider
from app.ai.mock import MockAddressProvider
from app.core.config import Settings


def create_provider(settings: Settings) -> AddressProvider:
    if settings.ai_provider in {"mock", "disabled"}:
        # The legacy demo endpoint always remains a visible fixed mock.
        return MockAddressProvider()
    raise ValueError("Unsupported AI provider")


def create_extraction_provider(settings: Settings) -> AddressExtractionProvider:
    factories = {"mock": MockExtractionProvider, "disabled": DisabledExtractionProvider}
    return factories[settings.ai_provider]()
