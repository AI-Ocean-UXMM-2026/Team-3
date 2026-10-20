from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.extraction import AddressExtractionProvider
from app.api.routes import get_extraction_provider
from app.core.dev_access import get_actor, get_session, require_dev_access
from app.core.order_errors import OrderAPIError
from app.db.models import User
from app.domain.lifecycle import OrderStatus, UserRole
from app.schemas.errors import ErrorResponse
from app.schemas.management import (
    ChangeStatus,
    CorrectOrder,
    CreateOrder,
    EventPage,
    OrderPage,
    OrderResponse,
    UserResponse,
)
from app.schemas.orders import Confidence, ParseRequest
from app.services.deterministic import DeterministicOrderParsingService
from app.services.hybrid import HybridOrderParsingService
from app.services.order_management import OrderManagementService

router = APIRouter(
    prefix="/api",
    tags=["local order management"],
    dependencies=[Depends(require_dev_access)],
    responses={code: {"model": ErrorResponse} for code in (401, 403, 404, 409, 422, 503)},
)
SessionDep = Annotated[Session, Depends(get_session)]
ActorDep = Annotated[User, Depends(get_actor)]
Page = Annotated[int, Query(ge=1, le=1000000)]
PageSize = Annotated[int, Query(ge=1, le=100)]


def service(request: Request, session: Session, actor: User):
    return OrderManagementService(
        session,
        actor,
        request.app.state.location_catalog,
        require_cod_confirmation=request.app.state.settings.rider_require_cod_confirmation,
    )


@router.post("/orders", response_model=OrderResponse, status_code=201)
async def create_order(
    body: CreateOrder,
    request: Request,
    session: SessionDep,
    actor: ActorDep,
    extractor: Annotated[AddressExtractionProvider, Depends(get_extraction_provider)],
):
    parsed = None
    mode = "structured"
    if body.raw_text is not None:
        settings = request.app.state.settings
        mode = "hybrid" if settings.parser_mode == "hybrid" else "rules"
        parser = (
            HybridOrderParsingService(request.app.state.location_catalog, extractor, settings)
            if mode == "hybrid"
            else DeterministicOrderParsingService(request.app.state.location_catalog)
        )
        parsed = await parser.parse(ParseRequest(raw_text=body.raw_text))
    return service(request, session, actor).create(body, parsed, mode)


@router.get("/orders", response_model=OrderPage)
def list_orders(
    request: Request,
    session: SessionDep,
    actor: ActorDep,
    page: Page = 1,
    page_size: PageSize = 20,
    status: OrderStatus | None = None,
    confidence: Confidence | None = None,
    q: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
):
    if q is not None and not q.strip():
        raise OrderAPIError(422, "VALIDATION_ERROR", "Search text must not be blank.")
    return service(request, session, actor).list(
        page, page_size, status, confidence, q.strip() if q is not None else None
    )


@router.get("/orders/{order_id:uuid}", response_model=OrderResponse)
def get_order(order_id: UUID, request: Request, session: SessionDep, actor: ActorDep):
    return OrderResponse.model_validate(service(request, session, actor).get(order_id))


@router.patch("/orders/{order_id:uuid}", response_model=OrderResponse)
def correct_order(
    order_id: UUID, body: CorrectOrder, request: Request, session: SessionDep, actor: ActorDep
):
    return service(request, session, actor).correct(order_id, body)


@router.patch("/orders/{order_id:uuid}/status", response_model=OrderResponse)
def change_status(
    order_id: UUID, body: ChangeStatus, request: Request, session: SessionDep, actor: ActorDep
):
    return service(request, session, actor).change_status(order_id, body)


@router.get("/orders/{order_id:uuid}/events", response_model=EventPage)
def get_events(
    order_id: UUID,
    request: Request,
    session: SessionDep,
    actor: ActorDep,
    page: Page = 1,
    page_size: PageSize = 20,
):
    return service(request, session, actor).events(order_id, page, page_size)


@router.get("/users", response_model=list[UserResponse])
def list_users(
    session: SessionDep,
    actor: ActorDep,
    role: UserRole | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
):
    query = select(User)
    if actor.role == UserRole.MERCHANT:
        query = query.where(User.id == actor.id)
    if role is not None:
        query = query.where(User.role == role)
    return session.scalars(query.order_by(User.name, User.id).limit(limit)).all()
