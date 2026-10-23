from datetime import timedelta

import pytest
from test_automatic_assignment import auto, confirmed, respond
from test_three_role_workflow import save, workspace  # noqa: F401, F811

from app.db.models import utcnow


@pytest.fixture
def tracked(workspace, monkeypatch):  # noqa: F811
    result = save(auto(workspace, confirmed(workspace)))
    accepted = save(respond(workspace, result, "ACCEPT"))
    result["order"]["version"] = accepted["order_version"]
    rider = result["assignment"]["rider_id"]
    key = next(k for k, v in workspace[1].items() if str(v) == rider)
    url = f"/api/riders/{rider}/deliveries/{result['order']['id']}/tracking"
    return workspace, result, key, url


def test_assigned_rider_and_buyer_share_the_same_road_route(tracked, monkeypatch):
    work, result, key, url = tracked
    geometry = {"type": "LineString", "coordinates": [[96.1, 16.8], [96.11, 16.81]]}
    monkeypatch.setattr(
        "app.services.delivery_tracking.road_route",
        lambda *_: {
            "geometry": geometry,
            "distance_meters": 1800,
            "duration_seconds": 300,
        },
    )
    before = save(work[0]["admin"].get(f"/api/orders/{result['order']['id']}"))["version"]
    posted = save(work[0][key].post(url, json={"latitude": 16.8, "longitude": 96.1}))
    assert posted["state"] == "live"
    assert posted["route"]["geometry"] == geometry
    lookup = save(
        work[0]["admin"].post(
            "/api/confirm/lookup",
            json={
                "tracking_id": result["order"]["id"],
                "phone": "09791234567",
            },
        )
    )
    target = f"/api/confirm/{lookup['token']}/tracking"
    assert work[0]["admin"].get(target).status_code == 401
    buyer = save(
        work[0]["admin"].get(target, headers={"Authorization": "Bearer " + lookup["access_token"]})
    )
    assert buyer == posted
    assert save(work[0]["admin"].get(f"/api/orders/{result['order']['id']}"))["version"] == before
    assert work[0]["admin"].post(url, json={"latitude": 16.8, "longitude": 96.1}).status_code == 403
    other = "other" if key == "rider" else "rider"
    assert work[0][other].get(url).status_code == 404


def test_tracking_rejects_invalid_and_out_of_order_positions(tracked, monkeypatch):
    work, _, key, url = tracked
    monkeypatch.setattr("app.services.delivery_tracking.road_route", lambda *_: None)
    assert work[0][key].post(url, json={"latitude": 91, "longitude": 96}).status_code == 422
    now = utcnow()
    first = save(
        work[0][key].post(
            url, json={"latitude": 16.8, "longitude": 96.1, "captured_at": now.isoformat()}
        )
    )
    older = save(
        work[0][key].post(
            url,
            json={
                "latitude": 16.7,
                "longitude": 96,
                "captured_at": (now - timedelta(seconds=5)).isoformat(),
            },
        )
    )
    assert older == first
    assert first["route"] is None


def test_tracking_stops_when_delivery_finishes(tracked, monkeypatch):
    work, result, key, url = tracked
    monkeypatch.setattr("app.services.delivery_tracking.road_route", lambda *_: None)
    save(work[0][key].post(url, json={"latitude": 16.8, "longitude": 96.1}))
    lookup = save(
        work[0]["admin"].post(
            "/api/confirm/lookup",
            json={"tracking_id": result["order"]["id"], "phone": "09791234567"},
        )
    )
    save(respond(work, result, "DELIVERED", actual_amount=25000, cod_collected=True))
    assert save(work[0][key].get(url))["state"] == "unavailable"
    buyer = work[0]["admin"].get(
        f"/api/confirm/{lookup['token']}/tracking",
        headers={"Authorization": "Bearer " + lookup["access_token"]},
    )
    assert buyer.status_code == 401
    assert work[0][key].post(url, json={"latitude": 16.8, "longitude": 96.1}).status_code == 409


def test_route_cache_expires_from_calculation_and_cumulative_movement(tracked, monkeypatch):
    work, _, key, url = tracked
    now = utcnow()
    calls = []

    def route(point, destination):
        calls.append(point)
        return {
            "geometry": {
                "type": "LineString",
                "coordinates": [
                    [point["lng"], point["lat"]],
                    [destination["lng"], destination["lat"]],
                ],
            },
            "distance_meters": 1800,
            "duration_seconds": 300,
        }

    monkeypatch.setattr("app.services.delivery_tracking.road_route", route)
    for seconds, latitude, expected in [
        (0, 16.8, 1),
        (15, 16.8004, 1),
        (25, 16.8008, 2),
        (60, 16.8009, 3),
    ]:
        instant = now + timedelta(seconds=seconds)
        monkeypatch.setattr("app.services.delivery_tracking.utcnow", lambda: instant)
        save(
            work[0][key].post(
                url,
                json={"latitude": latitude, "longitude": 96.1, "captured_at": instant.isoformat()},
            )
        )
        assert len(calls) == expected


def test_old_rider_cannot_read_a_reassigned_delivery(tracked, monkeypatch):
    from uuid import UUID, uuid4

    from app.db.rider_models import DeliveryAssignment

    work, result, key, url = tracked
    other = "other" if key == "rider" else "rider"
    with work[2].sessions.begin() as session:
        old = session.get(DeliveryAssignment, UUID(result["assignment"]["id"]))
        old.status = "UNASSIGNED"
        old.ended_at = utcnow()
        session.flush()
        session.add(
            DeliveryAssignment(
                id=uuid4(),
                order_id=old.order_id,
                rider_id=work[1][other],
                dispatcher_id=old.dispatcher_id,
                status="ACTIVE",
                response_status="ACCEPTED",
                responded_at=utcnow(),
            )
        )
    assert work[0][key].get(url).status_code == 404


@pytest.mark.parametrize("age,expected", [(120, "stale"), (601, "unavailable")])
def test_last_fix_is_labelled_stale_then_withheld(tracked, monkeypatch, age, expected):
    from uuid import UUID

    from app.db.rider_models import DeliveryPosition

    work, result, key, url = tracked
    monkeypatch.setattr("app.services.delivery_tracking.road_route", lambda *_: None)
    save(work[0][key].post(url, json={"latitude": 16.8, "longitude": 96.1}))
    with work[2].sessions.begin() as session:
        session.get(DeliveryPosition, UUID(result["assignment"]["id"])).captured_at = (
            utcnow() - timedelta(seconds=age)
        )
    assert save(work[0][key].get(url))["state"] == expected


@pytest.mark.parametrize(
    "status,coordinates,available",
    [
        (200, [[96.1, 16.8], [96.12, 16.82]], True),
        (200, [[96.1, 91], [96.12, 16.82]], False),
        (503, [[96.1, 16.8], [96.12, 16.82]], False),
    ],
)
def test_road_provider_geometry_and_failure(monkeypatch, status, coordinates, available):
    import httpx2 as httpx

    from app.services import delivery_tracking

    real_client = httpx.Client

    def handle(request):
        assert request.url.host == "router.project-osrm.org"
        return httpx.Response(
            status,
            json={
                "routes": [
                    {
                        "geometry": {"type": "LineString", "coordinates": coordinates},
                        "distance": 1800,
                        "duration": 300,
                    }
                ]
            },
        )

    monkeypatch.setattr(
        delivery_tracking.httpx,
        "Client",
        lambda **kwargs: real_client(transport=httpx.MockTransport(handle), **kwargs),
    )
    result = delivery_tracking.road_route({"lat": 16.8, "lng": 96.1}, {"lat": 16.82, "lng": 96.12})
    assert (result is not None) == available
