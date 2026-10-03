from unittest.mock import patch

import httpx
import pytest
from django.test import override_settings

from planner.errors import RoutingError
from planner.route_client import Location, OpenRouteServiceClient


@override_settings(ORS_API_KEY="test-key", ORS_API_BASE_URL="https://api.heigit.org")
@patch("planner.route_client.httpx.request")
def test_location_search_uses_current_pelias_endpoint(request):
    request.return_value = httpx.Response(
        200,
        json={
            "features": [
                {
                    "geometry": {"coordinates": [-97.7431, 30.2672]},
                    "properties": {"label": "Austin, TX, USA", "gid": "locality.1"},
                }
            ]
        },
    )

    results = OpenRouteServiceClient().search_locations("Austin")

    assert results[0].label == "Austin, TX, USA"
    request.assert_called_once_with(
        "GET",
        "https://api.heigit.org/pelias/v1/search",
        headers={"Authorization": "test-key", "Accept": "application/json"},
        timeout=20,
        params={"text": "Austin", "size": 5},
    )


@override_settings(ORS_API_KEY="test-key", ORS_API_BASE_URL="https://api.heigit.org")
@patch("planner.route_client.httpx.request")
def test_reverse_geocoding_uses_current_pelias_endpoint(request):
    request.return_value = httpx.Response(
        200,
        json={
            "features": [
                {"properties": {"locality": "Austin", "region_a": "TX"}}
            ]
        },
    )

    result = OpenRouteServiceClient().reverse((-97.7431, 30.2672))

    assert result == "Austin, TX"
    assert request.call_args.args[1] == "https://api.heigit.org/pelias/v1/reverse"
    assert request.call_args.kwargs["params"] == {
        "point.lon": -97.7431,
        "point.lat": 30.2672,
        "size": 1,
    }
    assert request.call_args.kwargs["timeout"] == 5


@override_settings(ORS_API_KEY="test-key", ORS_API_BASE_URL="https://api.heigit.org")
@patch("planner.route_client.httpx.request")
def test_directions_preserve_waypoint_order_and_convert_duration(request):
    request.return_value = httpx.Response(
        200,
        json={
            "features": [
                {
                    "geometry": {
                        "coordinates": [[-97.74, 30.27], [-96.80, 32.78], [-95.37, 29.76]]
                    },
                    "properties": {
                        "summary": {"distance": 400.5, "duration": 28_800},
                        "segments": [
                            {"distance": 200.0, "duration": 14_400, "steps": []},
                            {"distance": 200.5, "duration": 14_400, "steps": []},
                        ],
                    },
                }
            ]
        },
    )
    locations = [
        Location("Austin", (-97.74, 30.27), "austin"),
        Location("Dallas", (-96.80, 32.78), "dallas"),
        Location("Houston", (-95.37, 29.76), "houston"),
    ]

    route = OpenRouteServiceClient().directions(locations)

    assert route.distance_miles == 400.5
    assert route.duration_minutes == 480
    assert request.call_args.kwargs["headers"]["Accept"] == "application/geo+json"
    assert request.call_args.args[1].endswith(
        "/openrouteservice/v2/directions/driving-hgv/geojson"
    )
    assert request.call_args.kwargs["json"]["coordinates"] == [
        [-97.74, 30.27],
        [-96.8, 32.78],
        [-95.37, 29.76],
    ]
    assert request.call_args.kwargs["json"]["units"] == "mi"


@override_settings(ORS_API_KEY="test-key", ORS_API_BASE_URL="https://api.heigit.org")
@patch("planner.route_client.httpx.request", side_effect=httpx.TimeoutException("timeout"))
def test_provider_timeout_has_stable_error(_request):
    with pytest.raises(RoutingError) as error:
        OpenRouteServiceClient().search_locations("Austin")

    assert error.value.default_code == "routing_error"
    assert error.value.status_code == 504
    assert error.value.get_codes() == "routing_timeout"


@override_settings(ORS_API_KEY="test-key", ORS_API_BASE_URL="https://api.heigit.org")
def test_ambiguous_location_is_rejected():
    client = OpenRouteServiceClient()
    client.search_locations = lambda query, limit: [
        Location("Austin, TX, USA", (-97.74, 30.27), "austin"),
        Location("Austin, MN, USA", (-93.0, 43.7), "austin-mn"),
    ]

    with pytest.raises(RoutingError) as error:
        client.geocode_one("Austin")

    assert error.value.get_codes() == "ambiguous_location"


@override_settings(ORS_API_KEY="test-key", ORS_API_BASE_URL="https://api.heigit.org")
@patch("planner.route_client.httpx.request")
def test_incomplete_route_legs_are_not_fabricated(request):
    request.return_value = httpx.Response(
        200,
        json={
            "features": [
                {
                    "geometry": {"coordinates": [[-97.74, 30.27], [-95.37, 29.76]]},
                    "properties": {
                        "summary": {"distance": 400, "duration": 28_800},
                        "segments": [],
                    },
                }
            ]
        },
    )
    locations = [
        Location("Austin", (-97.74, 30.27), "austin"),
        Location("Dallas", (-96.8, 32.78), "dallas"),
        Location("Houston", (-95.37, 29.76), "houston"),
    ]

    with pytest.raises(RoutingError) as error:
        OpenRouteServiceClient().directions(locations)

    assert error.value.get_codes() == "invalid_routing_response"


@override_settings(ORS_API_KEY="test-key", ORS_API_BASE_URL="https://api.heigit.org")
@patch("planner.route_client.httpx.request")
def test_malformed_provider_json_has_stable_error(request):
    request.return_value = httpx.Response(200, text="not-json")

    with pytest.raises(RoutingError) as error:
        OpenRouteServiceClient().search_locations("Austin")

    assert error.value.get_codes() == "invalid_routing_response"
