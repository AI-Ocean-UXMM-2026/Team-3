import hashlib
import logging
import re
import secrets
import tempfile
import threading
from contextlib import ExitStack
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select, update

from app.core.config import Settings
from app.db.buyer_models import BuyerOtpChallenge, BuyerSession, ConfirmationLink
from app.db.migrations import upgrade_database
from app.db.models import User
from app.db.session import Database
from app.domain.lifecycle import ALLOWED_TRANSITIONS, UserRole
from app.main import create_app


class NoHTTPClientLogs(logging.Filter):
    def filter(self, record):
        # The HTTP client normally logs full URLs, including buyer capabilities.
        return False


class Sandbox:
    """Own every resource; reset replaces only this object's generated temporary directory."""

    def __init__(self):
        self.lock = threading.RLock()
        self._open()

    def _open(self):
        self.resources = ExitStack()
        try:
            for name in ("httpx", "httpx2"):
                logger = logging.getLogger(name)
                guard = NoHTTPClientLogs()
                logger.addFilter(guard)
                self.resources.callback(logger.removeFilter, guard)
            directory = self.storage_directory()
            self.directory = Path(directory)
            self.database = Database(
                f"sqlite+pysqlite:///{(self.directory / 'sandbox.sqlite3').as_posix()}"
            )
            self.resources.callback(self.database.dispose)
            upgrade_database(self.database)
            with self.database.sessions.begin() as session:
                identifiers = []
                for name, email, role in [
                    ("Test Dispatcher", "dispatch@example.invalid", UserRole.DISPATCHER),
                    ("Fictional Clothing Merchant", "merchant@example.invalid", UserRole.MERCHANT),
                ]:
                    user = session.scalar(select(User).where(User.email == email))
                    if user is None:
                        user = User(id=uuid4(), name=name, email=email, role=role)
                        session.add(user)
                    if user.role != role:
                        raise RuntimeError("Unexpected sandbox actor role")
                    identifiers.append(user.id)
                self.dispatcher_id, self.merchant_id = identifiers
            self.clients, self.buyers, self.workspace_buyers = {}, {}, {}
            self.generation = uuid4().hex
            self.dispatcher = self.client(self.dispatcher_id)
            # No privileged token on public buyer calls. Actual loopback peer, normal limits.
            self.public = self.resources.enter_context(
                TestClient(self.dispatcher.app, client=("127.0.0.1", 55002))
            )
            with self.database.sessions() as session:
                rider_exists = session.scalar(select(User.id).where(User.role == UserRole.RIDER))
            if rider_exists is None:
                response = self.dispatcher.post(
                    "/api/riders",
                    json={"name": "Test Rider One", "operational_status": "AVAILABLE"},
                )
                if response.status_code != 201:
                    raise RuntimeError("Could not initialize the fictional rider")
        except BaseException:
            self.resources.close()
            raise

    def storage_directory(self):
        return self.resources.enter_context(
            tempfile.TemporaryDirectory(prefix="lannpya-dashboard-")
        )

    def client(self, actor):
        if actor not in self.clients:
            settings = Settings(
                _env_file=None,
                environment="test",
                order_management_enabled=True,
                database_url="sqlite+pysqlite:///:memory:",
                dev_actor_id=actor,
                dev_access_token=secrets.token_urlsafe(32),
                parser_mode="hybrid",
                ai_provider="mock",
                ai_timeout_seconds=3.0,
                ai_max_input_chars=2000,
                cors_origins=[],
                buyer_frontend_base_url=None,
                buyer_link_hours=72,
                buyer_session_minutes=15,
                buyer_request_limit_per_minute=60,
                buyer_verify_limit_per_minute=10,
                buyer_otp_mode="demo",
                buyer_otp_external_sends_enabled=False,
                buyer_rescheduling_enabled=False,
                buyer_leave_with_security_enabled=False,
                buyer_cutoff_hour=15,
                buyer_min_notice_minutes=120,
                buyer_max_schedule_days=7,
                buyer_cross_township_fee_mmk=None,
                rider_require_cod_confirmation=True,
                rider_max_active_assignments=100,
            )
            application = create_app(settings, database=self.database)
            self.clients[actor] = self.resources.enter_context(
                TestClient(
                    application,
                    client=("127.0.0.1", 55001),
                    headers={"X-Dev-Access-Token": settings.dev_access_token.get_secret_value()},
                )
            )
        return self.clients[actor]

    def rider_client(self, rider_id):
        with self.database.sessions() as session:
            actor = session.get(User, rider_id)
            if actor is None or actor.role != UserRole.RIDER:
                return None
        return self.client(rider_id)

    def bootstrap(self):
        return {
            "test_mode": True,
            "generation": self.generation,
            "merchant_id": str(self.merchant_id),
            "ai": "MOCK — no external AI calls",
            "database": "isolated temporary SQLite; removed at reset/shutdown",
            "transitions": {str(k): sorted(map(str, v)) for k, v in ALLOWED_TRANSITIONS.items()},
        }

    def expire(self, handle, owner, kind):
        buyer = self.buyers.get(handle)
        if buyer is None or buyer["owner"] != owner:
            return False
        with self.database.sessions.begin() as session:
            when = datetime.now(UTC) - timedelta(minutes=1)
            if kind == "LINK":
                link = session.get(ConfirmationLink, UUID(buyer["link_id"]))
                link.expires_at = when
            else:
                session.execute(
                    update(BuyerSession)
                    .where(BuyerSession.link_id == UUID(buyer["link_id"]))
                    .values(expires_at=when)
                )
        return True

    def demo_otp(self, handle, owner):
        buyer = self.buyers.get(handle)
        link_id = None
        if buyer is not None and buyer["owner"] == owner:
            link_id = UUID(buyer["link_id"])
        elif (owner, handle) in self.workspace_buyers and re.fullmatch(r"[A-Za-z0-9_-]{43}", handle):
            with self.database.sessions() as session:
                link = session.scalar(select(ConfirmationLink).where(
                    ConfirmationLink.token_hash == hashlib.sha256(handle.encode()).hexdigest()
                ))
                link_id = link.id if link else None
        if link_id is None:
            return None
        with self.database.sessions() as session:
            challenge = session.scalar(
                select(BuyerOtpChallenge)
                .where(
                    BuyerOtpChallenge.link_id == link_id,
                    BuyerOtpChallenge.status == "PENDING",
                    BuyerOtpChallenge.provider == "DEMO",
                    BuyerOtpChallenge.expires_at > datetime.now(UTC),
                    BuyerOtpChallenge.demo_code.is_not(None),
                )
                .order_by(BuyerOtpChallenge.created_at.desc())
            )
            if challenge is None:
                return None
            return {"simulation": True, "code": challenge.demo_code, "expires_at": challenge.expires_at}

    def reset(self):
        with self.lock:
            self.resources.close()
            self._open()
            return self.bootstrap()

    def close(self):
        with self.lock:
            self.resources.close()
