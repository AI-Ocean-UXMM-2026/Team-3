"""Verify bearer credentials with Supabase; never trust client roles or decoded JWTs."""

from uuid import UUID

import httpx2 as httpx
from fastapi import Request

from app.core.order_errors import OrderAPIError


def verify_user(settings, token: str, request: Request | None = None) -> UUID:
    try:
        with httpx.Client(timeout=5.0, follow_redirects=False, trust_env=False) as client:
            response = client.get(
                settings.supabase_url + "/auth/v1/user",
                headers={
                    "apikey": settings.supabase_publishable_key,
                    "Authorization": "Bearer " + token,
                },
            )
        if response.status_code in {401, 403}:
            raise OrderAPIError(401, "AUTH_REQUIRED", "Sign in again to continue.")
        if response.status_code != 200:
            raise OrderAPIError(503, "AUTH_UNAVAILABLE", "Sign-in is temporarily unavailable.")
        user = response.json()
        if not user.get("email_confirmed_at") or user.get("is_anonymous"):
            raise OrderAPIError(403, "EMAIL_VERIFICATION_REQUIRED", "Verify your email first.")
        if request is not None:
            request.state.auth_user = user
        return UUID(user["id"])
    except OrderAPIError:
        raise
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        raise OrderAPIError(
            503, "AUTH_UNAVAILABLE", "Sign-in is temporarily unavailable."
        ) from None


def require_supabase_access(request: Request) -> None:
    if (
        not request.app.state.settings.order_management_enabled
        or request.app.state.database is None
    ):
        raise OrderAPIError(503, "ORDER_MANAGEMENT_DISABLED", "Order management is unavailable.")
    authorization = request.headers.get("Authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token or len(token) > 8192:
        raise OrderAPIError(401, "AUTH_REQUIRED", "Sign in to continue.")
    request.state.auth_subject = verify_user(request.app.state.settings, token, request)
