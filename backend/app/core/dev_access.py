import hmac
import ipaddress

from fastapi import Depends, Request
from fastapi.security import APIKeyHeader, HTTPBearer
from sqlalchemy.orm import Session

from app.core.order_errors import OrderAPIError
from app.db.models import User
from app.domain.lifecycle import UserRole

access_header = APIKeyHeader(
    name="X-Dev-Access-Token",
    auto_error=False,
    description="Local-only development token; not production authentication.",
)
bearer_header = HTTPBearer(
    auto_error=False,
    description="Supabase user access token when Supabase authentication is enabled.",
)


def require_dev_access(
    request: Request, token: str | None = Depends(access_header), bearer=Depends(bearer_header)
) -> None:
    settings = request.app.state.settings
    if settings.supabase_auth_enabled:
        from app.core.supabase_auth import require_supabase_access

        require_supabase_access(request)
        return
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
    subject = (
        getattr(request.state, "auth_subject", None)
        if request.app.state.settings.supabase_auth_enabled
        else request.app.state.settings.dev_actor_id
    )
    actor = session.get(User, subject) if subject else None
    if actor is None and request.app.state.settings.supabase_auth_enabled and subject:
        settings = request.app.state.settings
        if getattr(settings, "auto_provision_users", False):
            auth_user = getattr(request.state, "auth_user", None)
            if auth_user and auth_user.get("email_confirmed_at"):
                meta = (
                    auth_user.get("user_metadata")
                    or auth_user.get("raw_user_meta_data")
                    or {}
                )
                role_hint = str(meta.get("role") or meta.get("intended_role") or "").capitalize()
                role = UserRole.RIDER if role_hint == "Rider" else UserRole.DISPATCHER
                name = (
                    meta.get("shop_name")
                    or meta.get("shop")
                    or meta.get("name")
                    or (auth_user.get("email", "").split("@")[0] if auth_user.get("email") else "User")
                )
                email = auth_user.get("email") or f"{subject}@users.invalid"
                actor = User(
                    id=subject,
                    name=str(name)[:200],
                    email=str(email)[:254],
                    role=role,
                )
                session.add(actor)
                session.commit()
    if actor is None:
        if request.app.state.settings.supabase_auth_enabled:
            raise OrderAPIError(
                403, "ACCOUNT_NOT_PROVISIONED", "Your hub has not enabled this account yet."
            )
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
