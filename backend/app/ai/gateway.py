"""Provider-independent validation, timeout, and degradation boundary."""

import asyncio
import json
import logging
import re
from dataclasses import dataclass

from pydantic import ValidationError

from app.ai.base import AIProviderError
from app.ai.extraction import (
    AddressExtractionProvider,
    AIExtractionResponse,
    ExtractionRateLimitError,
    ExtractionTimeoutError,
    SanitizedAddressInput,
)
from app.schemas.orders import AIAvailability

logger = logging.getLogger(__name__)


def unique_keys(pairs: list[tuple]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate AI JSON key")
        result[key] = value
    return result


def reject_constant(value: str) -> None:
    raise ValueError("Non-JSON numeric constant")


@dataclass(frozen=True)
class ExtractionResult:
    availability: AIAvailability
    output: AIExtractionResponse | None = None


class ExtractionGateway:
    def __init__(
        self, provider: AddressExtractionProvider, timeout_seconds: float, *, allow_external=False
    ):
        self.provider = provider
        self.timeout_seconds = timeout_seconds
        self.allow_external = allow_external

    async def extract(self, payload: SanitizedAddressInput) -> ExtractionResult:
        # Public identifiers must be declared in adapter code, never derived from secrets.
        try:
            name = self.provider.name
            name = (
                name
                if isinstance(name, str)
                and re.fullmatch(
                    r"[a-z][a-z0-9_-]{0,63}",
                    name,
                )
                else "custom"
            )
            external, mock = self.provider.is_external, self.provider.is_mock
            if type(external) is not bool or type(mock) is not bool:
                raise ValueError("Invalid provider metadata")
        except Exception:
            logger.warning("AI extraction degraded: invalid_adapter_metadata")
            return ExtractionResult(
                AIAvailability(
                    status="unavailable",
                    message="AI adapter is unavailable. Deterministic results retained.",
                )
            )
        if external and not self.allow_external:
            return ExtractionResult(
                AIAvailability(
                    status="unavailable",
                    provider=name,
                    message=("External AI calls are not enabled. Deterministic results retained."),
                )
            )
        if name == "disabled":
            return ExtractionResult(
                AIAvailability(
                    status="disabled",
                    provider=name,
                    message="AI assistance is disabled. Deterministic results retained.",
                )
            )
        state = AIAvailability(provider=name, is_mock=mock, attempted=True)
        try:
            raw = await asyncio.wait_for(
                self.provider.extract(payload, timeout_seconds=self.timeout_seconds),
                timeout=self.timeout_seconds,
            )
        except (TimeoutError, ExtractionTimeoutError):
            state.status = "timeout"
            state.message = "AI request timed out. Deterministic results retained."
        except ExtractionRateLimitError as exc:
            state.status = "rate_limited"
            state.retry_after_seconds = exc.retry_after_seconds
            state.message = "AI provider is rate limited. Deterministic results retained."
        except AIProviderError:
            state.status = "unavailable"
            state.message = "AI provider is unavailable. Deterministic results retained."
        except Exception:
            # No exception repr, traceback, payload, or SDK HTTP headers in logs.
            state.status = "unavailable"
            state.message = "AI provider failed. Deterministic results retained."
        else:
            try:
                if type(raw) is not str or len(raw) > 16384:
                    raise ValueError("Invalid AI response size or type")
                data = json.loads(
                    raw, object_pairs_hook=unique_keys, parse_constant=reject_constant
                )
                output = AIExtractionResponse.model_validate(data, strict=True)
            except (ValueError, TypeError, ValidationError, RecursionError):
                state.status = "invalid_response"
                state.message = "AI response failed validation. Deterministic results retained."
            else:
                if mock:
                    state.status = "mock"
                    state.message = (
                        "Mock AI adapter: AI-derived fields are unavailable; "
                        "no simulated values were merged."
                    )
                    return ExtractionResult(state)
                state.status = "available"
                state.message = (
                    "AI response validated; any suggestions still require dispatcher review."
                )
                return ExtractionResult(state, output)
        logger.warning("AI extraction degraded: %s", state.status)
        return ExtractionResult(state)
