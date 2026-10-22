from datetime import date
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import func, select

from app.api.order_management import Page, PageSize, SessionDep
from app.api.riders import RiderActor
from app.core.dev_access import require_dev_access
from app.db.workflow_models import WorkflowRoute
from app.domain.lifecycle import UserRole
from app.schemas.management import OrderResponse
from app.services import workflow

router = APIRouter(
    prefix="/api", tags=["three-role workflow"], dependencies=[Depends(require_dev_access)]
)


class RouteCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rider_id: UUID
    day: date


class RouteAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: UUID
    expected_version: int = Field(ge=1, strict=True)
    action: Literal["DISPATCH", "HANDOVER", "RECEIVE_CLOSE", "CLOSE"]
    amount: int | None = Field(default=None, ge=0, le=1000000000, strict=True)
    recorded_total: int | None = Field(default=None, ge=0, strict=True)
    reason: str | None = Field(default=None, max_length=500)
    resolve: bool = Field(default=False, strict=True)


class OrderOperation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1, strict=True)
    action: Literal[
        "RECEIVE", "RETURN_RECEIVED", "RESOLVE_DIFFERENCE", "INCIDENT", "RESOLVE_INCIDENT"
    ]
    reason: str | None = Field(default=None, max_length=500)


class PrepareAssignment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: UUID
    expected_version: int = Field(ge=1, strict=True)
    route_id: UUID | None = None
    rider_id: UUID | None = None
    receive_at_hub: bool = Field(default=False, strict=True)
    acknowledge_unverified_location: bool = Field(default=False, strict=True)

    @model_validator(mode="after")
    def one_route_choice(self):
        if (self.route_id is None) == (self.rider_id is None):
            raise ValueError("Choose either an existing route or a rider for a new route.")
        return self


@router.get("/session")
def session_info(request: Request, actor: RiderActor) -> dict:
    return {
        "id": str(actor.id),
        "name": actor.name,
        "role": actor.role.value,
        "local_only": not request.app.state.settings.supabase_auth_enabled,
    }


@router.get("/routes")
def list_routes(
    session: SessionDep, actor: RiderActor, page: Page = 1, page_size: PageSize = 20
) -> dict:
    query = select(WorkflowRoute)
    if actor.role == UserRole.RIDER:
        query = query.where(WorkflowRoute.rider_id == actor.id)
    total = session.scalar(select(func.count()).select_from(query.subquery()))
    rows = session.scalars(
        query.order_by(WorkflowRoute.id).offset((page - 1) * page_size).limit(page_size)
    )
    return {
        "items": [workflow.response(session, r) for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/routes", status_code=201)
def create_route(body: RouteCreate, session: SessionDep, actor: RiderActor) -> dict:
    return workflow.create_route(session, actor, body)


@router.post("/routes/{route_id:uuid}/actions")
def route_action(route_id: UUID, body: RouteAction, session: SessionDep, actor: RiderActor) -> dict:
    return workflow.route_action(session, actor, route_id, body)


@router.post("/orders/{order_id:uuid}/operations", response_model=OrderResponse)
def order_operation(order_id: UUID, body: OrderOperation, session: SessionDep, actor: RiderActor):
    return workflow.order_operation(session, actor, order_id, body)


@router.post("/orders/{order_id:uuid}/prepare-assignment")
def prepare_assignment(
    order_id: UUID,
    body: PrepareAssignment,
    request: Request,
    session: SessionDep,
    actor: RiderActor,
) -> dict:
    return workflow.prepare_assignment(
        session,
        actor,
        order_id,
        body,
        request.app.state.settings,
        request.app.state.location_catalog,
    )
