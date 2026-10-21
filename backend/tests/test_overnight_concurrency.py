# Imported fixtures are intentionally injected again as test arguments by pytest.
# ruff: noqa: F811
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from test_buyer_confirmation import ADMIN, env, linked, verified  # noqa: F401
from test_riders import HEADERS, act, assign, order, queue, rider, saved
from test_riders import env as rider_env  # noqa: F401

from app.db.buyer_models import BuyerRequest
from app.db.models import DeliveryEvent, Order
from app.db.rider_models import DeliveryAssignment


def parallel_requests(app, calls):
    def request(call):
        with TestClient(app, client=("127.0.0.1", 54001)) as client:
            return client.request(**call)

    with ThreadPoolExecutor(max_workers=len(calls)) as pool:
        return list(pool.map(request, calls))


def test_two_dispatchers_assign_one_order_to_different_riders(rider_env):
    row = order(rider_env)
    riders = [rider(rider_env, name=f"Synthetic rider {i}") for i in range(2)]
    replies = parallel_requests(
        rider_env["app"],
        [
            {
                "method": "POST",
                "url": f"/api/orders/{row['id']}/assign",
                "headers": HEADERS,
                "json": {"expected_version": row["version"], "rider_id": who["id"]},
            }
            for who in riders
        ],
    )
    assert sorted(r.status_code for r in replies) == [201, 409]
    with rider_env["db"].sessions() as session:
        assert session.scalar(select(func.count()).select_from(DeliveryAssignment)) == 1
        assert (
            session.scalar(
                select(func.count())
                .select_from(DeliveryEvent)
                .where(DeliveryEvent.event_type == "RIDER_ASSIGNED")
            )
            == 1
        )


def test_concurrent_successful_verification_only_latest_session_authorizes(linked):
    replies = parallel_requests(
        linked["app"],
        [
            {"method": "POST", "url": linked["path"] + "/verify", "json": {"last_four": "4567"}}
            for _ in range(2)
        ],
    )
    assert all(r.status_code == 200 for r in replies)
    results = [
        linked["client"]
        .get(
            linked["path"] + "/details",
            headers={"Authorization": "Bearer " + r.json()["access_token"]},
        )
        .status_code
        for r in replies
    ]
    assert sorted(results) == [200, 401]


def test_buyer_pin_racing_dispatch_readiness_cannot_bypass_review(linked):
    row = linked["order"]
    credential = verified(linked)
    current = (
        linked["client"]
        .patch(
            f"/api/orders/{row['id']}/status",
            headers=ADMIN,
            json={"expected_version": row["version"], "status": "CONFIRMED"},
        )
        .json()
    )
    replies = parallel_requests(
        linked["app"],
        [
            {
                "method": "PATCH",
                "url": f"/api/orders/{row['id']}/status",
                "headers": ADMIN,
                "json": {
                    "expected_version": current["version"],
                    "status": "READY_FOR_DISPATCH",
                    "acknowledge_unverified_location": True,
                },
            },
            {
                "method": "PATCH",
                "url": linked["path"] + "/location",
                "headers": credential,
                "json": {
                    "request_id": str(uuid4()),
                    "latitude": 0,
                    "longitude": 0,
                    "initial_pin_acknowledged": True,
                },
            },
        ],
    )
    assert sorted(r.status_code for r in replies) == [200, 409]
    with linked["db"].sessions() as session:
        row = session.get(Order, UUID(row["id"]))
        pending = session.scalar(select(func.count()).select_from(BuyerRequest))
        assert (row.status == "NEEDS_REVIEW" and pending == 1) or (
            row.status == "READY_FOR_DISPATCH" and pending == 0
        )
        assert row.latitude is None and row.longitude is None


def test_distinct_completion_requests_do_not_duplicate_completion_event(rider_env):
    who, row = rider(rider_env), order(rider_env)
    assign(rider_env, row, who)
    assert act(rider_env, who, saved(rider_env, row["id"]), "START").status_code == 200
    current = saved(rider_env, row["id"])
    replies = parallel_requests(
        rider_env["app"],
        [
            {
                "method": "PATCH",
                "url": f"/api/riders/{who['id']}/deliveries/{row['id']}/status",
                "headers": HEADERS,
                "json": {
                    "request_id": str(uuid4()),
                    "expected_version": current["version"],
                    "action": "DELIVERED",
                    "cod_collected": True,
                },
            }
            for _ in range(2)
        ],
    )
    assert sorted(r.status_code for r in replies) == [200, 404]
    with rider_env["db"].sessions() as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(DeliveryEvent)
                .where(DeliveryEvent.event_type == "DELIVERY_COMPLETED")
            )
            == 1
        )


def test_assigned_unavailable_rider_cannot_start_until_available(rider_env):
    who, row = rider(rider_env), order(rider_env)
    assign(rider_env, row, who)
    profile = rider_env["client"].get(f"/api/riders/{who['id']}", headers=HEADERS).json()
    response = rider_env["client"].patch(
        f"/api/riders/{who['id']}",
        headers=HEADERS,
        json={"expected_version": profile["version"], "operational_status": "OFFLINE"},
    )
    assert response.status_code == 200
    assert queue(rider_env, who)["total"] == 1
    assert act(rider_env, who, saved(rider_env, row["id"]), "START").status_code == 409
    assert saved(rider_env, row["id"])["status"] == "ASSIGNED"


def test_nul_search_is_rejected_before_database_query(rider_env):
    response = rider_env["client"].get("/api/orders", headers=HEADERS, params={"q": "bad\x00query"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
