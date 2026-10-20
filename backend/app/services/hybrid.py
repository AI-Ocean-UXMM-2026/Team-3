import logging
import re

from app.ai.extraction import AddressExtractionProvider, AIExtractionResponse
from app.ai.gateway import ExtractionGateway
from app.ai.sanitization import PreparedAIRequest, prepare_ai_request
from app.core.config import Settings
from app.parsing.places import LocationCatalog
from app.parsing.triage import classify
from app.schemas.orders import (
    AIAvailability,
    ExtractionEvidence,
    FieldSource,
    ParseRequest,
    ParseResponse,
    ValidationReason,
)
from app.services.deterministic import DeterministicOrderParsingService

logger = logging.getLogger(__name__)


def grounded_suggestions(
    parsed: ParseResponse,
    prepared: PreparedAIRequest,
    output: AIExtractionResponse,
) -> dict[str, tuple[str, ExtractionEvidence]]:
    validated = {}
    fragments = {f.id: f for f in prepared.payload.fragments}
    for field in AIExtractionResponse.model_fields:
        suggestion = getattr(output, field)
        if suggestion is None:
            continue
        if field not in prepared.payload.requested_fields:
            raise ValueError("Unrequested AI field")
        fragment = fragments.get(suggestion.fragment_id)
        if fragment is None or suggestion.value not in suggestion.quote:
            raise ValueError("Ungrounded AI value")
        matches = list(re.finditer(re.escape(suggestion.quote), fragment.text))
        if len(matches) != 1:
            raise ValueError("AI evidence must uniquely identify an input span")
        start = prepared.origins[fragment.id] + matches[0].start()
        end = start + len(suggestion.quote)
        if parsed.normalized_text[start:end] != suggestion.quote:
            # A quote crossing a redacted phone/name span cannot be reconstituted.
            raise ValueError("AI evidence crosses a redacted span")
        validated[field] = (
            suggestion.value,
            ExtractionEvidence(
                value=suggestion.value,
                matched_text=suggestion.quote,
                start=start,
                end=end,
            ),
        )
    return validated


class HybridOrderParsingService:
    def __init__(
        self, catalog: LocationCatalog, provider: AddressExtractionProvider, settings: Settings
    ):
        self.catalog, self.provider, self.settings = catalog, provider, settings

    async def parse(self, request: ParseRequest) -> ParseResponse:
        parsed = await DeterministicOrderParsingService(self.catalog).parse(request)
        if self.settings.ai_provider == "disabled":
            parsed.ai = AIAvailability(
                status="disabled",
                provider="disabled",
                message="AI assistance is disabled. Deterministic results retained.",
            )
            return parsed
        unsafe_encoding = any(
            w.code in {"ENCODING_UNCERTAIN", "ZAWGYI_CONVERSION_FAILED"}
            for w in parsed.normalization.warnings
        )
        if unsafe_encoding:
            parsed.ai = AIAvailability(
                status="privacy_blocked",
                message="Uncertain text encoding prevents a safe AI payload; confirm Unicode text.",
            )
            return parsed
        prepared = prepare_ai_request(parsed, self.settings.ai_max_input_chars)
        if prepared is None:
            parsed.ai = AIAvailability(
                message=(
                    "No necessary allowlisted address fragment is available; no AI request made."
                )
            )
            return parsed
        result = await ExtractionGateway(self.provider, self.settings.ai_timeout_seconds).extract(
            prepared.payload,
        )
        parsed.ai = result.availability
        if result.output is not None:
            try:
                suggestions = grounded_suggestions(parsed, prepared, result.output)
            except ValueError:
                logger.warning("AI extraction degraded: ungrounded_response")
                parsed.ai.status = "invalid_response"
                parsed.ai.message = (
                    "AI suggestions were not grounded in sanitized input. "
                    "Deterministic results retained."
                )
            else:
                for field, (value, evidence) in suggestions.items():
                    source = parsed.field_sources[field]
                    if source.status == "missing":
                        setattr(parsed.address, field, value)
                        parsed.field_sources[field] = FieldSource(
                            method="ai",
                            status="extracted",
                            rule="grounded-ai-suggestion-v1",
                            evidence=[evidence],
                            provider=parsed.ai.provider,
                            requires_review=True,
                        )
                        parsed.ai.applied_fields.append(field)
                    else:
                        # AI cannot resolve competing deterministic evidence by fiat.
                        source.ai_suggestion = value
                        source.provider = parsed.ai.provider
                        source.requires_review = True
                        parsed.ai.suggested_fields.append(field)
        confidence, reasons, verification = classify(
            parsed.address,
            parsed.field_sources,
            parsed.normalization,
            self.catalog,
        )
        parsed.confidence, parsed.validation_reasons = confidence, reasons
        parsed.location_verification = verification
        if parsed.ai.applied_fields or parsed.ai.suggested_fields:
            parsed.validation_reasons.append(
                ValidationReason(
                    code="AI_FIELD_REVIEW",
                    message="AI suggestions are unverified; review these fields before dispatch.",
                )
            )
        if parsed.ai.status in {"timeout", "rate_limited", "invalid_response", "unavailable"}:
            parsed.validation_reasons.append(
                ValidationReason(
                    code=f"AI_{parsed.ai.status.upper()}",
                    message=parsed.ai.message,
                )
            )
        parsed.manual_review_required = (
            parsed.confidence != "GREEN"
            or bool(parsed.ai.applied_fields or parsed.ai.suggested_fields)
            or parsed.ai.status in {"timeout", "rate_limited", "invalid_response", "unavailable"}
        )
        parsed.notice = (
            "Rules-first extraction with optional AI assistance. Check AI availability and field "
            "sources; no location coordinates or delivery pin verification are produced."
        )
        return parsed
