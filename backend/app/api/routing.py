from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select

from app.api.order_management import Page, PageSize, SessionDep
from app.api.riders import RiderActor
from app.core.dev_access import require_dev_access
from app.core.order_errors import OrderAPIError
from app.db.routing_models import RoutingPlan
from app.domain.lifecycle import UserRole
from app.routing.factory import provider_for
from app.schemas.errors import ErrorResponse
from app.schemas.routing import (
    GoogleEstimate,
    GoogleEstimateQuery,
    GoogleEstimateStatus,
    MatrixQuery,
    PlanCommit,
    PlanPage,
    PlanQuery,
    PlanResponse,
    RoadMatrix,
    RoadRoute,
    RouteQuery,
    RoutingStatus,
)
from app.services import google_estimates
from app.services import route_planning as planning

router = APIRouter(
    prefix="/api",
    tags=["routing and optimization"],
    dependencies=[Depends(require_dev_access)],
    responses={
        code: {"model": ErrorResponse} for code in (401, 403, 404, 409, 422, 429, 502, 503, 504)
    },
)


def provider(request, allow_simulation):
    return getattr(request.app.state, "routing_provider_override", None) or provider_for(
        request.app.state.settings, allow_simulation
    )


@router.get("/routes/google-demo/status", response_model=GoogleEstimateStatus)
def google_status(request: Request, actor: RiderActor):
    google_estimates.permitted(actor)
    return google_estimates.status(request.app.state.settings)


@router.post("/routes/google-demo", response_model=GoogleEstimate)
def google_estimate(
    body: GoogleEstimateQuery, request: Request, session: SessionDep, actor: RiderActor
):
    return google_estimates.estimate(
        session,
        actor,
        request.app.state.settings,
        body,
        transport=getattr(request.app.state, "google_demo_transport_override", None),
    )


@router.get("/routes/provider-status", response_model=RoutingStatus)
def status(request: Request, actor: RiderActor):
    planning.dispatcher(actor)
    s = request.app.state.settings
    return {
        "provider": s.routing_provider,
        "external_requests_enabled": s.routing_external_requests_enabled,
        "key_configured": bool(
            s.google_routes_api_key if s.routing_provider == "google" else s.ors_api_key
        )
        if s.routing_provider in {"google", "ors"}
        else False,
        "simulation_acknowledgement_required": s.routing_provider == "offline",
        "max_stops": s.routing_max_stops,
        "live_verified": False,
        "two_wheeler_enabled": s.routing_provider == "google" and s.routing_two_wheeler_enabled,
    }


@router.post("/routes/calculate", response_model=RoadRoute)
def calculate(body: RouteQuery, request: Request, session: SessionDep, actor: RiderActor):
    planning.charge(session, actor, request.app.state.settings)
    return provider(request, body.allow_simulation).get_route(body)


@router.post("/routes/matrix", response_model=RoadMatrix)
def matrix(body: MatrixQuery, request: Request, session: SessionDep, actor: RiderActor):
    planning.charge(session, actor, request.app.state.settings)
    if len(body.locations) > request.app.state.settings.routing_max_stops + 1:
        raise OrderAPIError(422, "ROUTING_STOP_LIMIT", "Matrix exceeds the configured stop limit.")
    return provider(request, body.allow_simulation).get_route_matrix(body)


@router.post("/routes/optimize", status_code=201, response_model=PlanResponse)
def preview(body: PlanQuery, request: Request, session: SessionDep, actor: RiderActor):
    s = request.app.state.settings
    planning.charge(session, actor, s)
    return planning.preview(session, actor, s, body, provider(request, body.allow_simulation))


@router.get("/routes/plans", response_model=PlanPage)
def plans(
    request: Request,
    session: SessionDep,
    actor: RiderActor,
    page: Page = 1,
    page_size: PageSize = 20,
):
    planning.dispatcher(actor)
    total = session.scalar(select(func.count()).select_from(RoutingPlan))
    records = session.scalars(
        select(RoutingPlan)
        .order_by(RoutingPlan.created_at.desc(), RoutingPlan.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return {
        "items": [planning.output(session, p, request.app.state.settings) for p in records],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/routes/plans/{plan_id}", response_model=PlanResponse)
def get_plan(plan_id: UUID, request: Request, session: SessionDep, actor: RiderActor):
    planning.dispatcher(actor)
    return planning.output(
        session, planning.load_plan(session, plan_id), request.app.state.settings
    )


@router.post("/routes/plans/{plan_id}/commit", response_model=PlanResponse)
def commit(
    plan_id: UUID, body: PlanCommit, request: Request, session: SessionDep, actor: RiderActor
):
    planning.dispatcher(actor)
    return planning.commit(
        session,
        actor,
        request.app.state.settings,
        plan_id,
        body,
        request.app.state.location_catalog,
    )


@router.get("/riders/{rider_id}/route-plans", response_model=PlanPage)
def rider_plans(rider_id: UUID, request: Request, session: SessionDep, actor: RiderActor):
    if actor.role == UserRole.RIDER and actor.id != rider_id:
        raise OrderAPIError(403, "RIDER_SCOPE", "Only this rider's plan is available.")
    own = (
        RoutingPlan.state == "COMMITTED",
        RoutingPlan.data["routes"][str(rider_id)].as_string().is_not(None),
    )
    total = session.scalar(select(func.count()).select_from(RoutingPlan).where(*own))
    records = session.scalars(
        select(RoutingPlan)
        .where(*own)
        .order_by(RoutingPlan.created_at.desc(), RoutingPlan.id)
        .limit(20)
    )
    items = [planning.output(session, p, request.app.state.settings, rider_id) for p in records]
    return {"items": items, "total": total, "page": 1, "page_size": 20}
