from pydantic import ValidationError

from app.ai.base import AddressProvider, AIProviderError, ProviderInput, ProviderOutput
from app.schemas.orders import Confidence, ParseRequest, ParseResponse, ValidationReason


class OrderParsingService:
    def __init__(self, provider: AddressProvider):
        self.provider = provider

    async def parse(self, request: ParseRequest) -> ParseResponse:
        try:
            output = ProviderOutput.model_validate(
                await self.provider.parse(ProviderInput(raw_text=request.raw_text))
            )
        except ValidationError as exc:
            raise AIProviderError("Invalid provider response") from exc

        # Only the mock path is supported in Phase 1. Real classification rules need
        # agreed validation criteria; a provider cannot approve an address itself.
        if not output.is_mock:
            raise AIProviderError("Non-mock parsing is not enabled in Phase 1")
        return ParseResponse(
            is_mock=True,
            provider=self.provider.name,
            notice="MOCK DATA: no address extraction or verification has been performed.",
            address=output.address,
            confidence=Confidence.RED,
            validation_reasons=[
                ValidationReason(
                    code="MOCK_NOT_VERIFIED",
                    message="Mock output is not dispatch-ready; buyer confirmation is required.",
                ),
                *[
                    ValidationReason(code=f"MISSING_{field.upper()}", message=message)
                    for field, message in (
                        ("phone_number", "No validated customer phone number is available."),
                        ("township", "No validated township is available."),
                    )
                    if not getattr(output.address, field)
                ],
            ],
        )
