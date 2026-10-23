from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request

from app.api.order_management import Page, PageSize, SessionDep
from app.core.dev_access import get_rider_actor, require_dev_access
from app.db.models import User
from app.schemas.errors import ErrorResponse
from app.schemas.riders import (
    ActionResult,
    AssignmentPage,
    AssignmentResult,
    AssignOrder,
    DeliveryAction,
    OperationalStatus,
    QueueResponse,
    RiderCreate,
    RiderPage,
    RiderPatch,
    RiderResponse,
    SequencePatch,
    UnassignOrder,
)
from app.services import delivery_tracking
from app.services.riders import RiderService

router = APIRouter(
    prefix="/api",
    tags=["local rider copilot"],
    dependencies=[Depends(require_dev_access)],
    responses={code: {"model": ErrorResponse} for code in (401, 403, 404, 409, 422, 503)},
)
RiderActor = Annotated[User, Depends(get_rider_actor)]


@router.get("/riders/{rider_id:uuid}/deliveries/{order_id:uuid}/tracking")
def tracking(rider_id: UUID, order_id: UUID, session: SessionDep, actor: RiderActor):
    order = delivery_tracking.rider_order(session, actor, rider_id, order_id)
    return delivery_tracking.snapshot(session, order)


@router.post("/riders/{rider_id:uuid}/deliveries/{order_id:uuid}/tracking")
def share_position(
    rider_id: UUID,
    order_id: UUID,
    body: delivery_tracking.PositionReport,
    session: SessionDep,
    actor: RiderActor,
):
    return delivery_tracking.publish(session, actor, rider_id, order_id, body)


def service(request, session, actor):
    return RiderService(
        session, actor, request.app.state.settings, request.app.state.location_catalog
    )


@router.post("/riders", status_code=201, response_model=RiderResponse)
def create_rider(body: RiderCreate, request: Request, session: SessionDep, actor: RiderActor):
    return service(request, session, actor).create(body)


@router.get("/riders", response_model=RiderPage)
def list_riders(
    request: Request,
    session: SessionDep,
    actor: RiderActor,
    page: Page = 1,
    page_size: PageSize = 20,
    operational_status: OperationalStatus | None = None,
):
    return service(request, session, actor).list(page, page_size, operational_status)


@router.get("/riders/{rider_id:uuid}", response_model=RiderResponse)
def get_rider(rider_id: UUID, request: Request, session: SessionDep, actor: RiderActor):
    rider_service = service(request, session, actor)
    return rider_service.rider_response(*rider_service.rider(rider_id))


@router.patch("/riders/{rider_id:uuid}", response_model=RiderResponse)
def patch_rider(
    rider_id: UUID, body: RiderPatch, request: Request, session: SessionDep, actor: RiderActor
):
    return service(request, session, actor).patch(rider_id, body)


@router.get("/riders/{rider_id:uuid}/queue", response_model=QueueResponse)
def rider_queue(
    rider_id: UUID,
    request: Request,
    session: SessionDep,
    actor: RiderActor,
    cursor: Annotated[str | None, Query(pattern=r"^[a-f0-9]{64}$")] = None,
):
    return service(request, session, actor).queue(rider_id, cursor)


@router.post("/orders/{order_id:uuid}/assign", response_model=AssignmentResult, status_code=201)
def assign_order(
    order_id: UUID, body: AssignOrder, request: Request, session: SessionDep, actor: RiderActor
):
    return service(request, session, actor).assign(order_id, body)


@router.post("/orders/{order_id:uuid}/unassign", response_model=AssignmentResult)
def unassign_order(
    order_id: UUID, body: UnassignOrder, request: Request, session: SessionDep, actor: RiderActor
):
    return service(request, session, actor).unassign(order_id, body)


@router.patch("/orders/{order_id:uuid}/assignment", response_model=AssignmentResult)
def sequence_order(
    order_id: UUID, body: SequencePatch, request: Request, session: SessionDep, actor: RiderActor
):
    return service(request, session, actor).sequence(order_id, body)


@router.get("/orders/{order_id:uuid}/assignments", response_model=AssignmentPage)
def assignment_history(
    order_id: UUID,
    request: Request,
    session: SessionDep,
    actor: RiderActor,
    page: Page = 1,
    page_size: PageSize = 20,
):
    return service(request, session, actor).history(order_id, page, page_size)


@router.patch(
    "/riders/{rider_id:uuid}/deliveries/{order_id:uuid}/status", response_model=ActionResult
)
def delivery_action(
    rider_id: UUID,
    order_id: UUID,
    body: DeliveryAction,
    request: Request,
    session: SessionDep,
    actor: RiderActor,
):
    return service(request, session, actor).action(rider_id, order_id, body)
