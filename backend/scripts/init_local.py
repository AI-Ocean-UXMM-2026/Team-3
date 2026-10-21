"""Initialize private local SQLite storage; never overwrite an existing .env."""

import os
import secrets
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.engine import make_url

from app.core.config import Settings
from app.db.migrations import upgrade_database
from app.db.models import User
from app.db.session import BACKEND_ROOT, Database
from app.domain.lifecycle import UserRole


def main():
    path = BACKEND_ROOT / ".env"
    if not path.exists():
        # Copy non-secret parsing/CORS examples and append locally generated settings.
        initial = (BACKEND_ROOT / ".env.example").read_text(encoding="utf-8")
        token, actor = secrets.token_urlsafe(32), uuid4()
        # Example management settings remain disabled; override only in this new file.
        initial = "\n".join(
            line
            for line in initial.splitlines()
            if not line.startswith(
                (
                    "LANNPYA_ENVIRONMENT=",
                    "LANNPYA_DATABASE_URL=",
                    "LANNPYA_ORDER_MANAGEMENT_ENABLED=",
                    "LANNPYA_DEV_ACCESS_TOKEN=",
                    "LANNPYA_DEV_ACTOR_ID=",
                )
            )
        )
        initial += (
            "\nLANNPYA_ENVIRONMENT=local\nLANNPYA_ORDER_MANAGEMENT_ENABLED=true\n"
            "LANNPYA_DATABASE_URL=sqlite+pysqlite:///./data/lannpya_dev.sqlite3\n"
            f"LANNPYA_DEV_ACCESS_TOKEN={token}\nLANNPYA_DEV_ACTOR_ID={actor}\n"
        )
        with path.open("x", encoding="utf-8") as file:
            file.write(initial)
        os.chmod(path, 0o600)  # POSIX restriction; Windows ACLs remain OS-managed.
    settings = Settings()
    if (
        settings.environment != "local"
        or not settings.order_management_enabled
        or settings.dev_actor_id is None
        or not settings.dev_access_token
        or len(settings.dev_access_token.get_secret_value()) < 32
        or make_url(settings.database_url.get_secret_value()).get_backend_name() != "sqlite"
    ):
        raise SystemExit(
            "Local bootstrap requires enabled local SQLite settings and a configured actor/token. "
            "Existing settings were preserved."
        )
    database = Database(settings.database_url.get_secret_value())
    try:
        upgrade_database(database)
        with database.sessions.begin() as session:
            actor = session.get(User, settings.dev_actor_id)
            if actor is None:
                # Bootstrap is opt-in and limited to synthetic local operator profiles.
                if session.scalar(select(User).where(User.email == "dispatcher@lannpya.local")):
                    raise SystemExit(
                        "Local dispatcher already exists with a different ID; "
                        "no profile overwritten."
                    )
                session.add(
                    User(
                        id=settings.dev_actor_id,
                        name="Local Dispatcher",
                        email="dispatcher@lannpya.local",
                        role=UserRole.DISPATCHER,
                    )
                )
            if session.scalar(select(User).where(User.email == "merchant@lannpya.local")) is None:
                session.add(
                    User(
                        name="Local Merchant",
                        email="merchant@lannpya.local",
                        role=UserRole.MERCHANT,
                    )
                )
        print("Local SQLite database migrated; synthetic dispatcher/merchant profiles available.")
        print("Development access is configured in ignored backend/.env; token was not printed.")
        print(
            "No orders were seeded, no cloud service was contacted, "
            "and existing profiles were preserved."
        )
    finally:
        database.dispose()


if __name__ == "__main__":
    main()
