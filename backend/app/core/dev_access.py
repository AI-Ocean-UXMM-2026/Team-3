import hmac
import ipaddress

from fastapi import Depends, Request
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session

from app.core.order_errors import OrderAPIError
from app.db.models import User
from app.domain.lifecycle import UserRole

access_header = APIKeyHeader(
    name="X-Dev-Access-Token",
    auto_error=False,
    description="Local-only development token; not production authentication.",
)


def require_dev_access(request: Request, token: str | None = Depends(access_header)) -> None:
    settings = request.app.state.settings
    if (
        settings.environment not in {"local", "test"}
        or not settings.order_management_enabled
        or request.app.state.database is None
    ):
        raise OrderAPIError(
            503,
            "ORDER_MANAGEMENT_DISABLED",
            "Order management is unavailable in this configuration.",
        )
    try:
        local = request.client is not None and ipaddress.ip_address(request.client.host).is_loopback
    except ValueError:
        local = False
    if not local:
        raise OrderAPIError(
            403, "LOCAL_ACCESS_ONLY", "Order management allows loopback access only."
        )
    secret = settings.dev_access_token
    if not secret or len(secret.get_secret_value()) < 32 or settings.dev_actor_id is None:
        raise OrderAPIError(
            503, "DEV_ACCESS_NOT_CONFIGURED", "Local development access is not configured."
        )
    if (
        not token
        or len(token) > 512
        or not hmac.compare_digest(
            token.encode("utf-8"),
            secret.get_secret_value().encode("utf-8"),
        )
    ):
        raise OrderAPIError(
            401, "DEV_ACCESS_REQUIRED", "A valid development access token is required."
        )


def get_session(request: Request, access=Depends(require_dev_access)):
    with request.app.state.database.sessions() as session:
        try:
            yield session
        except Exception:
            session.rollback()
            raise


def get_bound_actor(request: Request, session: Session = Depends(get_session)) -> User:
    actor = session.get(User, request.app.state.settings.dev_actor_id)
    if actor is None:
        raise OrderAPIError(403, "DEV_ACTOR_UNAVAILABLE", "Development actor is unavailable.")
    return actor


def get_actor(actor: User = Depends(get_bound_actor)) -> User:
    if actor.role == UserRole.RIDER:
        raise OrderAPIError(403, "ROLE_FORBIDDEN", "This role cannot access order management.")
    return actor


def get_rider_actor(actor: User = Depends(get_bound_actor)) -> User:
    if actor.role not in {UserRole.RIDER, UserRole.DISPATCHER, UserRole.ADMIN}:
        raise OrderAPIError(
            403, "ROLE_FORBIDDEN", "Rider operations require a rider, dispatcher or admin."
        )
    return actor
