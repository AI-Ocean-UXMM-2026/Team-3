from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request

from app.api.order_management import ActorDep, Page, PageSize, SessionDep
from app.core.buyer_access import buyer_session, consume_rate_limit
from app.core.dev_access import require_dev_access
from app.schemas.buyer import (
    BuyerActionResult,
    BuyerAuthorizationResult,
    BuyerCardResult,
    BuyerDetailsResult,
    BuyerHistoryPage,
    BuyerOtpChallengeResult,
    BuyerLocation,
    BuyerLookup,
    BuyerLookupResult,
    BuyerResponse,
    BuyerRequestSubmission,
    BuyerReviewResult,
    LinkResult,
    LocationReferenceResult,
    ReviewBuyerRequest,
    RevocationResult,
    SetLocationReference,
    VerifyBuyer,
)
from app.schemas.errors import ErrorResponse
from app.services.buyer_confirmation import BuyerConfirmationService
from app.services.buyer_otp import BuyerOtpService

ERRORS = {
    code: {"model": ErrorResponse} for code in (401, 403, 404, 409, 410, 422, 423, 429, 500, 503)
}
public_router = APIRouter(prefix="/api/confirm", tags=["buyer confirmation"], responses=ERRORS)
protected_router = APIRouter(
    prefix="/api/orders",
    tags=["local buyer management"],
    dependencies=[Depends(require_dev_access)],
    responses=ERRORS,
)
PublicSession = Annotated[object, Depends(buyer_session)]
Authorization = Annotated[str | None, Header(max_length=512)]


def service(request, session):
    return BuyerConfirmationService(
        session,
        request.app.state.settings,
        request.app.state.location_catalog,
        request.app.state.township_boundaries,
    )


def credential(header):
    return header[7:] if header and header.startswith("Bearer ") else None


@protected_router.post(
    "/{order_id:uuid}/confirmation-link", status_code=201, response_model=LinkResult
)
def generate_link(order_id: UUID, request: Request, session: SessionDep, actor: ActorDep):
    return service(request, session).generate(order_id, actor)


@protected_router.post("/{order_id:uuid}/confirmation-link/revoke", response_model=RevocationResult)
def revoke_link(order_id: UUID, request: Request, session: SessionDep, actor: ActorDep):
    return service(request, session).revoke(order_id, actor)


@protected_router.post(
    "/{order_id:uuid}/location-reference", status_code=201, response_model=LocationReferenceResult
)
def location_reference(
    order_id: UUID,
    body: SetLocationReference,
    request: Request,
    session: SessionDep,
    actor: ActorDep,
):
    return service(request, session).set_reference(order_id, actor, body)


@protected_router.get("/{order_id:uuid}/buyer-requests", response_model=BuyerHistoryPage)
def buyer_history(
    order_id: UUID,
    request: Request,
    session: SessionDep,
    actor: ActorDep,
    page: Page = 1,
    page_size: PageSize = 20,
):
    return service(request, session).history(order_id, actor, page, page_size)


@public_router.post("/lookup", response_model=BuyerLookupResult)
def lookup(body: BuyerLookup, request: Request, session: PublicSession):
    consume_rate_limit(request, verify=True)
    return service(request, session).lookup(body.tracking_id, body.phone)


@public_router.get("/{token}", response_model=BuyerCardResult)
def card(token: str, request: Request, session: PublicSession):
    return service(request, session).card(token)


@protected_router.patch(
    "/{order_id:uuid}/buyer-requests/{request_id:uuid}", response_model=BuyerReviewResult
)
def review_buyer_request(
    order_id: UUID,
    request_id: UUID,
    body: ReviewBuyerRequest,
    request: Request,
    session: SessionDep,
    actor: ActorDep,
):
    return service(request, session).review(order_id, request_id, actor, body)


@public_router.post("/{token}/verify", response_model=BuyerAuthorizationResult)
def verify(token: str, body: VerifyBuyer, request: Request, session: PublicSession):
    consume_rate_limit(request, verify=True)
    return service(request, session).verify(token, body)


@public_router.post("/{token}/otp", response_model=BuyerOtpChallengeResult)
def start_otp(token: str, request: Request, session: PublicSession):
    consume_rate_limit(request, verify=True)
    return BuyerOtpService(session, request.app.state.settings).start(token)


@public_router.get("/{token}/details", response_model=BuyerDetailsResult)
def details(
    token: str, request: Request, session: PublicSession, authorization: Authorization = None
):
    return service(request, session).details(token, credential(authorization))


@public_router.patch("/{token}/location", response_model=BuyerActionResult)
def location(
    token: str,
    body: BuyerLocation,
    request: Request,
    session: PublicSession,
    authorization: Authorization = None,
):
    return service(request, session).location(token, credential(authorization), body)


@public_router.patch("/{token}/response", response_model=BuyerActionResult)
def response(
    token: str,
    body: BuyerResponse,
    request: Request,
    session: PublicSession,
    authorization: Authorization = None,
):
    return service(request, session).response(token, credential(authorization), body)


@public_router.patch("/{token}/request", response_model=BuyerActionResult)
def request_submission(
    token: str,
    body: BuyerRequestSubmission,
    request: Request,
    session: PublicSession,
    authorization: Authorization = None,
):
    return service(request, session).request_submission(token, credential(authorization), body)
