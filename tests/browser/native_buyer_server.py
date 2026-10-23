"""Isolated real API server for browser-held buyer authorization tests."""

import sys
import base64
import json
from threading import Thread
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import uvicorn

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.core.config import Settings
from app.db.migrations import upgrade_database
from app.db.models import User
from app.db.session import Database
from app.domain.lifecycle import UserRole
from app.parsing.places import LocationCatalog
from app.schemas.management import CreateOrder
from app.services.order_management import OrderManagementService
from tools import secure_workspace


def main():
    port, filename = int(sys.argv[1]), Path(sys.argv[2])
    url = "sqlite+pysqlite:///" + filename.as_posix()
    database = Database(url)
    upgrade_database(database)
    actor_id = uuid4()
    hub_mode = len(sys.argv) > 3 and sys.argv[3] == "hub-isolation"
    hub_ids = [UUID("11111111-1111-4111-8111-111111111111"),
               UUID("22222222-2222-4222-8222-222222222222")]
    if hub_mode:
        actor_id = hub_ids[0]
    with database.sessions.begin() as session:
        session.add(User(id=actor_id, name="Fictional dispatcher",
                         email="dispatcher@example.test", role=UserRole.DISPATCHER))
        if hub_mode:
            session.add(User(id=hub_ids[1], name="Fictional second hub",
                             email="second@example.test", role=UserRole.ADMIN))
    day = (datetime.now(UTC) + timedelta(days=1, hours=6, minutes=30)).date().isoformat()
    with database.sessions() as session:
        actor = session.get(User, actor_id)
        service = OrderManagementService(session, actor, LocationCatalog())
        for reference in ("NATIVE-A", "NATIVE-B"):
            if hub_mode:
                service = OrderManagementService(
                    session, session.get(User, hub_ids[reference == "NATIVE-B"]), LocationCatalog()
                )
            body = CreateOrder.model_validate({
                "structured": {"customer_name": reference if hub_mode else "Fictional buyer", "customer_phone": "09790000000",
                               "township": "Hlaing", "street": "Test street", "cod_amount": "0"},
                "parcel": {"item": "Test parcel", "reference": reference, "delivery_day": day},
            })
            service.create(body, None, "structured")
    settings = Settings(
        _env_file=None, environment="test", LANNPYA_DATABASE_URL=url,
        order_management_enabled=True, supabase_auth_enabled=True,
        supabase_url="https://auth.example.supabase.co",
        supabase_publishable_key="sb_publishable_test",
    )
    if len(sys.argv) > 3 and sys.argv[3] == "demo-otp":
        from app.services.buyer_confirmation import BuyerConfirmationService
        previews = []
        with database.sessions() as session:
            actor = session.get(User, actor_id)
            service = OrderManagementService(session, actor, LocationCatalog())
            for index, phone in enumerate(["09790000001", "09790000002"]):
                order = service.create(CreateOrder.model_validate({
                    "structured": {"customer_name": "Demo OTP buyer", "customer_phone": phone,
                                   "township": "Hlaing", "cod_amount": "0"},
                    "parcel": {"item": "Test parcel", "reference": f"DEMO-OTP-{index}", "delivery_day": day},
                }), None, "structured")
                link = BuyerConfirmationService(session, settings, LocationCatalog(), None).generate(order.id, actor)
                previews.append(link["confirmation_url"])
        filename.with_suffix(".links.json").write_text(json.dumps(previews), encoding="utf-8")
    database.dispose()
    assert settings.database_url.get_secret_value() == url
    if hub_mode:
        from app.core import supabase_auth

        def synthetic_identity(_settings, token, request=None):
            subject = UUID(json.loads(base64.urlsafe_b64decode(token.split(".")[1] + "=="))["sub"])
            assert subject in hub_ids
            return subject

        supabase_auth.verify_user = synthetic_identity
    # Use the production entry point and native public buyer API, with isolated settings.
    secure_workspace.Settings = lambda: settings
    server = uvicorn.Server(uvicorn.Config(
        secure_workspace.application(), host="127.0.0.1", port=port,
        access_log=False, log_level="warning",
    ))

    def stop_on_input():
        sys.stdin.readline()
        server.should_exit = True

    Thread(target=stop_on_input, daemon=True).start()
    server.run()


if __name__ == "__main__":
    main()
