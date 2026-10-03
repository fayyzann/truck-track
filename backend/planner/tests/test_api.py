from datetime import datetime
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from planner.errors import RoutingError
from planner.route_client import Location, Route, RouteLeg


@pytest.fixture
def api_client():
    return APIClient()


def fake_route() -> Route:
    return Route(
        coordinates=[(-97.74, 30.27), (-96.8, 32.78), (-95.37, 29.76)],
        distance_miles=400,
        duration_minutes=480,
        legs=[
            RouteLeg(200, 240, "Austin, TX", "Dallas, TX"),
            RouteLeg(200, 240, "Dallas, TX", "Houston, TX"),
        ],
        instructions=[{"instruction": "Head north", "distance_miles": 10}],
    )


def test_health(api_client):
    response = api_client.get(
        "/api/v1/health",
        HTTP_ACCEPT="text/html,application/xhtml+xml,*/*;q=0.8",
    )
    assert response.status_code == 200
    assert response["Content-Type"].startswith("application/json")
    assert response.json()["status"] == "ok"


def test_openapi_docs_render(api_client):
    response = api_client.get("/api/docs/")
    assert response.status_code == 200
    assert b"swagger-ui" in response.content


@patch("planner.views.OpenRouteServiceClient")
def test_trip_plan_contract(client_class, api_client):
    client = Mock()
    client_class.return_value = client
    client.geocode_one.side_effect = [
        Location("Austin, TX", (-97.74, 30.27), "austin"),
        Location("Dallas, TX", (-96.8, 32.78), "dallas"),
        Location("Houston, TX", (-95.37, 29.76), "houston"),
    ]
    client.directions.return_value = fake_route()
    client.reverse.return_value = "Waco, TX"

    response = api_client.post(
        "/api/v1/trips/plan",
        {
            "current_location": "Austin",
            "pickup_location": "Dallas",
            "dropoff_location": "Houston",
            "cycle_hours_used": "12.50",
            "departure_at": datetime(
                2026, 1, 5, 8, tzinfo=ZoneInfo("America/Chicago")
            ).isoformat(),
            "terminal_timezone": "America/Chicago",
            "log_metadata": {"driver_name": "Alex Morgan"},
        },
        format="json",
    )

    assert response.status_code == 200
    data = response.json()
    assert data["route"]["distance_miles"] == 400
    assert len(data["route"]["locations"]) == 3
    assert data["daily_logs"]
    assert data["compliance"]["is_compliant"] is True
    assert data["daily_logs"][0]["metadata"]["driver_name"] == "Alex Morgan"
    assert response["Cache-Control"] == "no-store"


def test_rejects_invalid_cycle_hours(api_client):
    response = api_client.post(
        "/api/v1/trips/plan",
        {
            "current_location": "Austin",
            "pickup_location": "Dallas",
            "dropoff_location": "Houston",
            "cycle_hours_used": 72,
            "departure_at": "2026-01-05T08:00:00-06:00",
            "terminal_timezone": "America/Chicago",
        },
        format="json",
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("terminal_timezone", "/etc/passwd"),
        ("terminal_timezone", "../UTC"),
        ("departure_at", "2026-01-05T08:00:00"),
        ("departure_at", "9999-12-31T23:30:00Z"),
    ],
)
def test_rejects_malformed_time_context(api_client, field, value):
    response = api_client.post(
        "/api/v1/trips/plan",
        {
            "current_location": "Austin",
            "pickup_location": "Dallas",
            "dropoff_location": "Houston",
            "cycle_hours_used": 0,
            "departure_at": "2026-01-05T08:00:00-06:00",
            "terminal_timezone": "America/Chicago",
            field: value,
        },
        format="json",
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid"


def test_rejects_oversized_location_query(api_client):
    response = api_client.get("/api/v1/locations", {"q": "a" * 241})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_query"


@patch("planner.views.OpenRouteServiceClient")
def test_location_search_is_throttled(client_class, api_client):
    cache.clear()
    client_class.return_value.search_locations.return_value = []

    for _ in range(60):
        assert api_client.get("/api/v1/locations", {"q": "Austin"}).status_code == 200
    response = api_client.get("/api/v1/locations", {"q": "Austin"})

    assert response.status_code == 429
    assert response.json()["error"]["code"] == "throttled"


@patch("planner.views.OpenRouteServiceClient")
def test_specific_routing_error_code_is_preserved(client_class, api_client):
    cache.clear()
    client_class.side_effect = RoutingError(
        "Quota exhausted.", code="routing_quota_exceeded", status_code=429
    )

    response = api_client.get("/api/v1/locations", {"q": "Austin"})

    assert response.status_code == 429
    assert response.json()["error"]["code"] == "routing_quota_exceeded"
