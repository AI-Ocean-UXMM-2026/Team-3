from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from test_three_role_workflow import action, manual, save, workspace  # noqa: F401

from app.db.buyer_models import BuyerRequest, ConfirmationLink
from app.db.models import Order, utcnow
from app.db.rider_models import DeliveryAssignment, RiderProfile


def confirmed(workspace, **kwargs):
    row = manual(workspace, **kwargs)
    with workspace[2].sessions.begin() as session:
        link = ConfirmationLink(
            order_id=UUID(row["id"]),
            token_hash=uuid4().hex * 2,
            phone_binding=uuid4().hex * 2,
            expires_at=utcnow() + timedelta(hours=1),
        )
        session.add(link)
        session.flush()
        session.add(
            BuyerRequest(
                order_id=UUID(row["id"]),
                link_id=link.id,
                request_id=uuid4(),
                payload_hash=uuid4().hex * 2,
                kind="RESPONSE",
                decision="APPLIED",
                reason_codes=[],
                previous_values={},
                submitted_values={"action": "AVAILABLE"},
            )
        )
    return row


def auto(workspace, row, **extra):
    return workspace[0]["admin"].post(
        f"/api/orders/{row['id']}/auto-assignment",
        json={
            "request_id": str(uuid4()),
            "expected_version": row["version"],
            "acknowledge_unverified_location": True,
            **extra,
        },
    )


def respond(workspace, result, kind, **extra):
    assignment = result["assignment"]
    key = next(k for k, v in workspace[1].items() if str(v) == assignment["rider_id"])
    body = {
        "request_id": str(uuid4()),
        "expected_version": result["order"]["version"],
        "action": kind,
        "assignment_id": assignment["id"],
        "offer_version": assignment["offer_version"],
        **extra,
    }
    return workspace[0][key].patch(
        f"/api/riders/{assignment['rider_id']}/deliveries/{result['order']['id']}/status",
        json=body,
    )


def test_real_response_required_and_role_guard(workspace):
    row = manual(workspace)
    assert auto(workspace, row).status_code == 409
    row = confirmed(workspace)
    response = workspace[0]["rider"].post(
        f"/api/orders/{row['id']}/auto-assignment",
        json={
            "request_id": str(uuid4()),
            "expected_version": row["version"],
            "acknowledge_unverified_location": True,
        },
    )
    assert response.status_code == 403


def test_acceptance_starts_delivery_and_preserves_dispatcher_closeout(workspace):
    result = save(auto(workspace, confirmed(workspace)))
    assert result["allocation_status"] == "ASSIGNED"
    assert result["assignment"]["response_status"] == "PENDING"
    assert result["assignment"]["rider_id"] == str(min(workspace[1][k] for k in ("rider", "other")))
    assert action(workspace[0]["admin"], result["route"], "DISPATCH").status_code == 409
    assert (
        respond(workspace, result, "DELIVERED", cod_collected=True, actual_amount=25000).status_code
        == 409
    )
    assert respond(workspace, result, "START").status_code == 409
    accepted = save(respond(workspace, result, "ACCEPT"))
    assert accepted["response_status"] == "ACCEPTED"
    assert accepted["status"] == "OUT_FOR_DELIVERY"
    result["order"]["version"] = accepted["order_version"]
    route = next(r for r in save(workspace[0]["admin"].get("/api/routes"))["items"]
                 if r["id"] == result["route"]["id"])
    assert route["state"] == "dispatched"
    assert route["items"][0]["status"] == "OUT_FOR_DELIVERY"
    current = save(workspace[0]["admin"].get(f"/api/orders/{result['order']['id']}"))
    result["order"] = current
    assert (
        save(respond(workspace, result, "DELIVERED", cod_collected=True, actual_amount=25000))[
            "status"
        ]
        == "DELIVERED"
    )
    assert route["state"] == "dispatched"
    rider_key = next(k for k, v in workspace[1].items()
                     if str(v) == result["assignment"]["rider_id"])
    handed = save(action(workspace[0][rider_key], route, "HANDOVER",
                         amount=25000, recorded_total=25000))
    closed = save(action(workspace[0]["admin"], handed, "RECEIVE_CLOSE", amount=25000))
    assert closed["state"] == "closed"


def test_decline_reassigns_excludes_and_replays_before_stale_checks(workspace):
    result = save(auto(workspace, confirmed(workspace)))
    request_id = str(uuid4())
    declined = save(respond(workspace, result, "DECLINE", request_id=request_id))
    assert declined["outcome"] == "REASSIGNED"
    assert declined["replacement_assignment"]["rider_id"] != result["assignment"]["rider_id"]
    assert save(respond(workspace, result, "DECLINE", request_id=request_id)) == declined
    assert respond(workspace, result, "ACCEPT").status_code in (404, 409)
    replacement = {
        "order": {"id": result["order"]["id"], "version": declined["order_version"]},
        "assignment": declined["replacement_assignment"],
    }
    exhausted = save(respond(workspace, replacement, "DECLINE"))
    assert exhausted["outcome"] == "WAITING_FOR_RIDER"
    assert exhausted["replacement_assignment"] is None
    current = save(workspace[0]["admin"].get(f"/api/orders/{result['order']['id']}"))
    retried = save(auto(workspace, current))
    assert retried["allocation_status"] == "WAITING_FOR_RIDER"
    routes = save(workspace[0]["admin"].get("/api/routes"))["items"]
    assert all(not r["items"] for r in routes)


def test_wait_receipt_readiness_and_availability_recovery(workspace):
    for key in ("rider", "other"):
        with workspace[2].sessions.begin() as session:
            session.get(RiderProfile, workspace[1][key]).operational_status = "OFFLINE"
    row = confirmed(workspace, received=False)
    request_id = str(uuid4())
    waiting = save(auto(workspace, row, request_id=request_id))
    assert waiting["allocation_status"] == "WAITING_FOR_READINESS"
    assert save(auto(workspace, row, request_id=request_id)) == waiting
    assert auto(workspace, row, request_id=request_id, receive_at_hub=True).status_code == 409
    received = save(
        workspace[0]["admin"].post(
            f"/api/orders/{row['id']}/operations",
            json={
                "expected_version": waiting["order"]["version"],
                "action": "RECEIVE",
            },
        )
    )
    assert received["parsing_metadata"]["parcel"]["allocation"]["status"] == "WAITING_FOR_RIDER"
    profile = save(workspace[0]["admin"].get(f"/api/riders/{workspace[1]['rider']}"))
    save(
        workspace[0]["admin"].patch(
            f"/api/riders/{workspace[1]['rider']}",
            json={
                "expected_version": profile["version"],
                "operational_status": "AVAILABLE",
            },
        )
    )
    queue = save(workspace[0]["rider"].get(f"/api/riders/{workspace[1]['rider']}/queue"))
    assert queue["items"][0]["response_status"] == "PENDING"
    assert queue["items"][0]["allocation_status"] == "ASSIGNED"


def test_concurrent_reconfirmation_reserves_only_one_order_per_free_rider(workspace):
    with workspace[2].sessions.begin() as session:
        session.get(RiderProfile, workspace[1]["other"]).operational_status = "ON_BREAK"
    rows = [confirmed(workspace), confirmed(workspace)]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda row: save(auto(workspace, row)), rows))
    assert sorted(r["allocation_status"] for r in results) == ["ASSIGNED", "WAITING_FOR_RIDER"]
    with workspace[2].sessions() as session:
        assert (
            len(
                list(
                    session.scalars(
                        select(DeliveryAssignment).where(DeliveryAssignment.status == "ACTIVE")
                    )
                )
            )
            == 1
        )


def test_dispatcher_cannot_accept_for_rider_and_wrong_offer_fails(workspace):
    result = save(auto(workspace, confirmed(workspace)))
    assignment = result["assignment"]
    body = {
        "action": "ACCEPT",
        "request_id": str(uuid4()),
        "expected_version": result["order"]["version"],
        "assignment_id": assignment["id"],
        "offer_version": assignment["offer_version"],
    }
    url = f"/api/riders/{assignment['rider_id']}/deliveries/{result['order']['id']}/status"
    assert workspace[0]["admin"].patch(url, json=body).status_code == 403
    assert respond(workspace, result, "ACCEPT", assignment_id=str(uuid4())).status_code == 409


@pytest.mark.parametrize("mutation", ["phone", "response", "revoked", "pending", "cancelled"])
def test_waiting_authorization_is_rechecked_before_recovery(workspace, mutation):
    from app.domain.lifecycle import OrderStatus

    for key in ("rider", "other"):
        with workspace[2].sessions.begin() as session:
            session.get(RiderProfile, workspace[1][key]).operational_status = "OFFLINE"
    row = confirmed(workspace)
    save(auto(workspace, row))
    with workspace[2].sessions.begin() as session:
        order = session.get(Order, UUID(row["id"]))
        buyer = session.scalar(select(BuyerRequest).where(BuyerRequest.order_id == order.id))
        if mutation == "phone":
            order.customer_phone = "09987654321"
        elif mutation == "revoked":
            session.get(ConfirmationLink, buyer.link_id).revoked_at = utcnow()
        elif mutation == "cancelled":
            order.status = OrderStatus.CANCELLED
        else:
            session.add(
                BuyerRequest(
                    order_id=order.id,
                    link_id=buyer.link_id,
                    request_id=uuid4(),
                    payload_hash=uuid4().hex * 2,
                    kind="RESPONSE",
                    decision="REVIEW_REQUIRED" if mutation == "pending" else "APPLIED",
                    reason_codes=[],
                    previous_values={},
                    submitted_values={"action": "AVAILABLE"},
                )
            )
    profile = save(workspace[0]["admin"].get(f"/api/riders/{workspace[1]['rider']}"))
    save(
        workspace[0]["admin"].patch(
            f"/api/riders/{workspace[1]['rider']}",
            json={
                "expected_version": profile["version"],
                "operational_status": "AVAILABLE",
            },
        )
    )
    queue = save(workspace[0]["rider"].get(f"/api/riders/{workspace[1]['rider']}/queue"))
    assert queue["total"] == 0


def test_delivery_completion_drains_waiting_order(workspace):
    with workspace[2].sessions.begin() as session:
        session.get(RiderProfile, workspace[1]["other"]).operational_status = "OFFLINE"
    first = save(auto(workspace, confirmed(workspace)))
    waiting = save(auto(workspace, confirmed(workspace)))
    assert waiting["allocation_status"] == "WAITING_FOR_RIDER"
    save(respond(workspace, first, "ACCEPT"))
    first["order"] = save(workspace[0]["admin"].get(f"/api/orders/{first['order']['id']}"))
    save(respond(workspace, first, "DELIVERED", actual_amount=25000, cod_collected=True))
    queue = save(workspace[0]["rider"].get(f"/api/riders/{workspace[1]['rider']}/queue"))
    assert [x["order_id"] for x in queue["items"]] == [waiting["order"]["id"]]


def test_simultaneous_accept_decline_applies_one_response(workspace):
    result = save(auto(workspace, confirmed(workspace)))
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(
            pool.map(lambda kind: respond(workspace, result, kind), ["ACCEPT", "DECLINE"])
        )
    assert sorted(r.status_code for r in responses)[0] == 200
    assert sorted(r.status_code for r in responses)[1] in (404, 409)
    with workspace[2].sessions() as session:
        assignments = session.scalars(
            select(DeliveryAssignment).where(
                DeliveryAssignment.order_id == UUID(result["order"]["id"]),
                DeliveryAssignment.status == "ACTIVE",
            )
        ).all()
        assert len(assignments) == 1


def test_startup_recovers_persisted_waiting_work(workspace):
    from fastapi.testclient import TestClient
    from test_three_role_workflow import SECRET

    from app.core.config import Settings
    from app.main import create_app

    with workspace[2].sessions.begin() as session:
        for key in ("rider", "other"):
            session.get(RiderProfile, workspace[1][key]).operational_status = "OFFLINE"
    result = save(auto(workspace, confirmed(workspace)))
    with workspace[2].sessions.begin() as session:
        session.get(RiderProfile, workspace[1]["rider"]).operational_status = "AVAILABLE"
    settings = Settings(
        _env_file=None,
        environment="local",
        order_management_enabled=True,
        dev_actor_id=workspace[1]["admin"],
        dev_access_token=SECRET,
    )
    with TestClient(create_app(settings, database=workspace[2]), client=("127.0.0.1", 50000)):
        with workspace[2].sessions() as session:
            assignment = session.scalar(
                select(DeliveryAssignment).where(
                    DeliveryAssignment.order_id == UUID(result["order"]["id"]),
                    DeliveryAssignment.status == "ACTIVE",
                )
            )
            assert assignment is not None
            assert assignment.response_status == "PENDING"


def test_revocation_blocks_acceptance_and_departure(workspace):
    result = save(auto(workspace, confirmed(workspace)))
    with workspace[2].sessions.begin() as session:
        link = session.scalar(
            select(ConfirmationLink).where(ConfirmationLink.order_id == UUID(result["order"]["id"]))
        )
        link.revoked_at = utcnow()
    assert respond(workspace, result, "ACCEPT").status_code == 409


def test_same_request_concurrent_reconfirm_is_immutable(workspace):
    row = confirmed(workspace)
    request_id = str(uuid4())
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(lambda _: save(auto(workspace, row, request_id=request_id)), range(2))
        )
    assert results[0] == results[1]
    with workspace[2].sessions() as session:
        assert len(session.scalars(select(DeliveryAssignment)).all()) == 1


def test_migration_preserves_existing_assignments_and_action_receipts(tmp_path):
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import MetaData, Table

    from app.db.models import User
    from app.db.session import BACKEND_ROOT, Database
    from app.domain.lifecycle import UserRole

    db = Database(f"sqlite+pysqlite:///{tmp_path / 'old.sqlite3'}")
    cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
    with db.engine.begin() as connection:
        cfg.attributes["connection"] = connection
        command.upgrade(cfg, "0005_routing_plans")
    rider_id, dispatcher_id, order_id, assignment_id = (uuid4() for _ in range(4))
    with db.sessions.begin() as session:
        session.add_all(
            [
                User(id=rider_id, name="Rider", email="r@example.test", role=UserRole.RIDER),
                User(id=dispatcher_id, name="Admin", email="a@example.test", role=UserRole.ADMIN),
            ]
        )
        session.flush()
        session.add(RiderProfile(id=rider_id))
        session.add(
            Order(
                id=order_id,
                merchant_id=dispatcher_id,
                confidence_level="RED",
                confidence_reasons=[],
                parsing_mode="structured",
                ai_availability_status="not_requested",
                field_sources={},
                parsing_metadata={},
            )
        )
    with db.engine.begin() as connection:
        metadata = MetaData()
        assignments = Table("delivery_assignments", metadata, autoload_with=connection)
        receipts = Table("rider_action_receipts", metadata, autoload_with=connection)
        connection.execute(
            assignments.insert().values(
                id=assignment_id.hex,
                order_id=order_id.hex,
                rider_id=rider_id.hex,
                dispatcher_id=dispatcher_id.hex,
                status="ACTIVE",
                assigned_at=utcnow(),
                updated_at=utcnow(),
            )
        )
        connection.execute(
            receipts.insert().values(
                id=uuid4().hex,
                actor_id=rider_id.hex,
                rider_id=rider_id.hex,
                order_id=order_id.hex,
                assignment_id=assignment_id.hex,
                request_id=uuid4().hex,
                payload_hash="a" * 64,
                result={"legacy": True},
                created_at=utcnow(),
            )
        )
    with db.engine.begin() as connection:
        cfg.attributes["connection"] = connection
        command.upgrade(cfg, "0006_automatic_assignment")
    with db.sessions() as session:
        assignment = session.get(DeliveryAssignment, assignment_id)
        assert assignment.response_status == "ACCEPTED"
        assert assignment.allocation_cycle is None
        from app.db.rider_models import RiderActionReceipt

        assert session.scalar(select(RiderActionReceipt)).result == {"legacy": True}
    db.dispose()
