from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from planner.logs import build_daily_logs
from planner.route_client import OpenRouteServiceClient
from planner.scheduler import HOSScheduler
from planner.serializers import TripPlanRequestSerializer


class HealthView(APIView):
    authentication_classes = []
    permission_classes = []

    @extend_schema(responses={200: dict})
    def get(self, request):
        return Response({"status": "ok", "service": "trucktrack-api"})


class LocationSearchView(APIView):
    authentication_classes = []
    permission_classes = []
    throttle_scope = "locations"

    @extend_schema(
        parameters=[OpenApiParameter(name="q", required=True, type=str)],
        responses={200: dict},
    )
    def get(self, request):
        query = request.query_params.get("q", "").strip()
        if len(query) < 2:
            return Response(
                {"error": {"code": "invalid_query", "message": "Enter at least two characters."}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(query) > 240:
            return Response(
                {
                    "error": {
                        "code": "invalid_query",
                        "message": "Location queries cannot exceed 240 characters.",
                    }
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        matches = OpenRouteServiceClient().search_locations(query)
        return Response({"results": [match.as_dict() for match in matches]})


class TripPlanView(APIView):
    authentication_classes = []
    permission_classes = []
    throttle_scope = "trip_plans"

    @extend_schema(request=TripPlanRequestSerializer, responses={200: dict})
    def post(self, request):
        serializer = TripPlanRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data

        client = OpenRouteServiceClient()
        locations = [
            client.geocode_one(payload["current_location"]),
            client.geocode_one(payload["pickup_location"]),
            client.geocode_one(payload["dropoff_location"]),
        ]
        route = client.directions(locations)
        scheduler = HOSScheduler(
            route,
            payload["departure_at"],
            float(payload["cycle_hours_used"]),
        )
        events, compliance = scheduler.build()

        warnings = [
            "Planned fuel and rest coordinates are route positions, not verified truck facilities.",
            (
                "Rolling recovery from prior duty days is unavailable; "
                "a 34-hour restart is used when needed."
            ),
        ]
        location_events = [
            event
            for event in events
            if event.reason in {"fuel", "break", "sleeper", "cycle_restart"}
        ]
        if location_events:
            with ThreadPoolExecutor(max_workers=min(4, len(location_events))) as executor:
                nearby_locations = executor.map(
                    client.reverse, (event.coordinate for event in location_events)
                )
                for event, nearby in zip(location_events, nearby_locations, strict=True):
                    if nearby:
                        event.location = nearby

        metadata = {key: str(value) for key, value in payload.get("log_metadata", {}).items()}
        logs = build_daily_logs(
            events,
            terminal_timezone=payload["terminal_timezone"],
            origin=locations[0].label,
            destination=locations[-1].label,
            metadata=metadata,
        )

        response = Response(
            {
                "route": {
                    "geojson": route.as_geojson(),
                    "distance_miles": round(route.distance_miles, 1),
                    "duration_minutes": round(route.duration_minutes),
                    "locations": [location.as_dict() for location in locations],
                    "legs": [
                        {
                            "start": leg.start_label,
                            "end": leg.end_label,
                            "distance_miles": round(leg.distance_miles, 1),
                            "duration_minutes": round(leg.duration_minutes),
                        }
                        for leg in route.legs
                    ],
                    "instructions": route.instructions,
                },
                "events": [event.as_dict() for event in events],
                "stops": [
                    event.as_dict()
                    for event in events
                    if event.reason
                    in {"pickup", "dropoff", "fuel", "break", "sleeper", "cycle_restart"}
                ],
                "daily_logs": logs,
                "compliance": compliance,
                "assumptions": [
                    "Property-carrying driver on the 70-hour/8-day schedule.",
                    "The driver begins after at least 10 consecutive hours off duty.",
                    "No adverse conditions, short-haul exception, or split-sleeper pairing.",
                    "Daily logs retain the terminal UTC offset in effect at departure.",
                    (
                        "Pickup and drop-off each take one hour; fueling takes "
                        "30 minutes every 1,000 miles."
                    ),
                ],
                "warnings": warnings,
            }
        )
        response["Cache-Control"] = "no-store"
        return response
