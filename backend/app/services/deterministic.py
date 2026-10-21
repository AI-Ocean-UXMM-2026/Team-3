from app.parsing.normalization import normalize_text
from app.parsing.places import LocationCatalog
from app.parsing.rules import extract_fields
from app.parsing.triage import classify
from app.schemas.orders import ParseRequest, ParseResponse


class DeterministicOrderParsingService:
    def __init__(self, catalog: LocationCatalog):
        self.catalog = catalog

    async def parse(self, request: ParseRequest) -> ParseResponse:
        text, normalization = normalize_text(request.raw_text)
        address, sources = extract_fields(text)
        confidence, reasons, verification = classify(address, sources, normalization, self.catalog)
        return ParseResponse(
            is_mock=False,
            provider="rules",
            notice=(
                "Deterministic local extraction only. No AI call, saved order, "
                "geocoding, or delivery pin verification."
            ),
            address=address,
            confidence=confidence,
            validation_reasons=reasons,
            original_text=request.raw_text,
            normalized_text=text,
            normalization=normalization,
            field_sources=sources,
            location_verification=verification,
            manual_review_required=confidence != "GREEN",
        )
