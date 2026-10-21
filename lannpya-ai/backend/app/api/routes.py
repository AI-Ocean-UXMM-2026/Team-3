from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.ai.base import AddressProvider
from app.ai.extraction import AddressExtractionProvider
from app.schemas.errors import ErrorResponse
from app.schemas.orders import HealthResponse, ParseRequest, ParseResponse
from app.services.deterministic import DeterministicOrderParsingService
from app.services.hybrid import HybridOrderParsingService
from app.services.orders import OrderParsingService

router = APIRouter()


def get_provider(request: Request) -> AddressProvider:
    return request.app.state.address_provider


def get_extraction_provider(request: Request) -> AddressExtractionProvider:
    return request.app.state.extraction_provider


@router.get("/health", response_model=HealthResponse, tags=["health"])
async def health() -> HealthResponse:
    return HealthResponse()


@router.post(
    "/api/orders/parse",
    response_model=ParseResponse,
    responses={422: {"model": ErrorResponse}, 502: {"model": ErrorResponse}},
    tags=["orders"],
    summary="Parse an order with rules-first hybrid assistance (external AI disabled)",
)
async def parse_order(
    payload: ParseRequest,
    request: Request,
    provider: Annotated[AddressProvider, Depends(get_provider)],
    extractor: Annotated[AddressExtractionProvider, Depends(get_extraction_provider)],
) -> ParseResponse:
    if request.app.state.parser_mode == "hybrid":
        return await HybridOrderParsingService(
            request.app.state.location_catalog,
            extractor,
            request.app.state.settings,
        ).parse(payload)
    if request.app.state.parser_mode == "rules":
        return await DeterministicOrderParsingService(request.app.state.location_catalog).parse(
            payload
        )
    return await OrderParsingService(provider).parse(payload)
