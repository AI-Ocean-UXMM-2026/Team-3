import hashlib
from datetime import UTC, datetime, timedelta

from fastapi import Request
from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.core.order_errors import OrderAPIError
from app.db.buyer_models import BuyerRateLimit


def public_database(request: Request):
    settings = request.app.state.settings
    database = request.app.state.database
    if (
        (
            settings.environment not in {"local", "test"}
            and not (
                settings.supabase_auth_enabled
                and settings.buyer_rate_limit_secret
                and len(settings.buyer_rate_limit_secret.get_secret_value()) >= 32
            )
        )
        or not settings.order_management_enabled
        or database is None
    ):
        raise OrderAPIError(
            503, "BUYER_CONFIRMATION_DISABLED", "Buyer confirmation is unavailable."
        )
    return database


def consume_rate_limit(request: Request, verify=False):
    """Shared atomic fixed-window counters; does not trust forwarded IP headers."""
    database = public_database(request)
    now = datetime.now(UTC)
    bucket = int(now.timestamp()) // 60
    scope = "verify" if verify else "public"
    peer = request.client.host if request.client else "unknown"
    # No plaintext IP is retained. Stable salted hashes work across app workers/restarts.
    secret = (
        request.app.state.settings.buyer_rate_limit_secret
        or request.app.state.settings.dev_access_token
    )
    salt = secret.get_secret_value() if secret else "local-buyer-rate-limiter"
    key = hashlib.sha256(f"{salt}:{peer}:{scope}:{bucket}".encode()).hexdigest()
    settings = request.app.state.settings
    limit = (
        settings.buyer_verify_limit_per_minute
        if verify
        else settings.buyer_request_limit_per_minute
    )
    insert = sqlite_insert if database.engine.dialect.name == "sqlite" else postgres_insert
    with database.sessions.begin() as session:
        session.execute(delete(BuyerRateLimit).where(BuyerRateLimit.expires_at < now))
        statement = insert(BuyerRateLimit).values(
            key=key,
            count=1,
            expires_at=datetime.fromtimestamp((bucket + 1) * 60, UTC) + timedelta(minutes=1),
        )
        statement = statement.on_conflict_do_update(
            index_elements=[BuyerRateLimit.key],
            set_={"count": BuyerRateLimit.count + 1},
            where=BuyerRateLimit.count < limit,
        ).returning(BuyerRateLimit.count)
        accepted = session.scalar(statement) is not None
    if not accepted:
        raise OrderAPIError(429, "BUYER_RATE_LIMITED", "Too many requests; retry after one minute.")


def buyer_session(request: Request):
    consume_rate_limit(request)
    with public_database(request).sessions() as session:
        try:
            yield session
        except Exception:
            session.rollback()
            raise
