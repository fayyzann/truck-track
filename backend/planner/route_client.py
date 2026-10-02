from __future__ import annotations

from dataclasses import dataclass
from math import asin, cos, radians, sin, sqrt
from typing import Any

import httpx
from django.conf import settings

from planner.errors import RoutingError

METERS_PER_MILE = 1609.344


@dataclass(frozen=True)
class Location:
    label: str
    coordinate: tuple[float, float]
    provider_id: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "coordinate": list(self.coordinate),
            "provider_id": self.provider_id,
        }


@dataclass(frozen=True)
class RouteLeg:
    distance_miles: float
    duration_minutes: float
    start_label: str
    end_label: str


@dataclass
class Route:
    coordinates: list[tuple[float, float]]
    distance_miles: float
    duration_minutes: float
    legs: list[RouteLeg]
    instructions: list[dict[str, Any]]

    def coordinate_at_mile(self, target_mile: float) -> tuple[float, float]:
        if not self.coordinates:
            return (0.0, 0.0)
        if target_mile <= 0:
            return self.coordinates[0]
        if target_mile >= self.distance_miles:
            return self.coordinates[-1]

        target_meters = target_mile * METERS_PER_MILE
        walked = 0.0
        for start, end in zip(self.coordinates, self.coordinates[1:], strict=False):
            segment = haversine_meters(start, end)
            if walked + segment >= target_meters:
                ratio = 0 if segment == 0 else (target_meters - walked) / segment
                return (
                    start[0] + (end[0] - start[0]) * ratio,
                    start[1] + (end[1] - start[1]) * ratio,
                )
            walked += segment
        return self.coordinates[-1]

    def as_geojson(self) -> dict[str, Any]:
        return {
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": self.coordinates},
            "properties": {
                "distance_miles": round(self.distance_miles, 1),
                "duration_minutes": round(self.duration_minutes),
            },
        }


def haversine_meters(start: tuple[float, float], end: tuple[float, float]) -> float:
    lon1, lat1 = map(radians, start)
    lon2, lat2 = map(radians, end)
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 6_371_000 * 2 * asin(sqrt(a))


class OpenRouteServiceClient:
    def __init__(self) -> None:
        if not settings.ORS_API_KEY:
            raise RoutingError(
                "Routing is not configured. Add ORS_API_KEY to the backend environment.",
                code="routing_not_configured",
                status_code=503,
            )
        self.base_url = settings.ORS_API_BASE_URL.rstrip("/")
        self.headers = {"Authorization": settings.ORS_API_KEY, "Accept": "application/json"}
        self.timeout = settings.ORS_TIMEOUT_SECONDS

    def search_locations(self, query: str, *, limit: int = 5) -> list[Location]:
        data = self._request(
            "GET",
            "/geocoding/v1/search",
            params={"text": query, "size": limit},
        )
        return [self._location_from_feature(feature) for feature in data.get("features", [])]

    def geocode_one(self, query: str) -> Location:
        matches = self.search_locations(query, limit=1)
        if not matches:
            raise RoutingError(
                f'No routable location was found for "{query}".',
                code="location_not_found",
                status_code=422,
            )
        return matches[0]

    def reverse(self, coordinate: tuple[float, float]) -> str | None:
        try:
            data = self._request(
                "GET",
                "/geocoding/v1/reverse",
                params={"point.lon": coordinate[0], "point.lat": coordinate[1], "size": 1},
            )
        except RoutingError:
            return None
        features = data.get("features", [])
        if not features:
            return None
        props = features[0].get("properties", {})
        locality = props.get("locality") or props.get("county") or props.get("label")
        region = props.get("region_a") or props.get("region")
        return ", ".join(part for part in (locality, region) if part)

    def directions(self, locations: list[Location]) -> Route:
        data = self._request(
            "POST",
            "/openrouteservice/v2/directions/driving-hgv/geojson",
            json={
                "coordinates": [list(location.coordinate) for location in locations],
                "instructions": True,
                "units": "mi",
                "language": "en",
            },
        )
        features = data.get("features", [])
        if not features:
            raise RoutingError(
                "No truck route was returned.",
                code="route_not_found",
                status_code=422,
            )

        feature = features[0]
        properties = feature.get("properties", {})
        summary = properties.get("summary", {})
        raw_segments = properties.get("segments", [])
        legs: list[RouteLeg] = []
        for index, segment in enumerate(raw_segments):
            if index + 1 >= len(locations):
                break
            legs.append(
                RouteLeg(
                    distance_miles=float(segment.get("distance", 0)),
                    duration_minutes=float(segment.get("duration", 0)) / 60,
                    start_label=locations[index].label,
                    end_label=locations[index + 1].label,
                )
            )

        if len(legs) != len(locations) - 1:
            total_distance = float(summary.get("distance", 0))
            total_duration = float(summary.get("duration", 0)) / 60
            even_distance = total_distance / max(1, len(locations) - 1)
            even_duration = total_duration / max(1, len(locations) - 1)
            legs = [
                RouteLeg(even_distance, even_duration, locations[i].label, locations[i + 1].label)
                for i in range(len(locations) - 1)
            ]

        instructions: list[dict[str, Any]] = []
        for leg_index, segment in enumerate(raw_segments):
            for step in segment.get("steps", []):
                instructions.append(
                    {
                        "leg_index": leg_index,
                        "instruction": step.get("instruction", "Continue"),
                        "name": step.get("name", ""),
                        "distance_miles": round(float(step.get("distance", 0)), 1),
                        "duration_minutes": round(float(step.get("duration", 0)) / 60, 1),
                    }
                )

        coordinates = [tuple(point) for point in feature.get("geometry", {}).get("coordinates", [])]
        return Route(
            coordinates=coordinates,
            distance_miles=float(summary.get("distance", sum(leg.distance_miles for leg in legs))),
            duration_minutes=float(summary.get("duration", 0)) / 60
            or sum(leg.duration_minutes for leg in legs),
            legs=legs,
            instructions=instructions,
        )

    def _request(self, method: str, path: str, **kwargs) -> dict[str, Any]:
        try:
            response = httpx.request(
                method,
                f"{self.base_url}{path}",
                headers=self.headers,
                timeout=self.timeout,
                **kwargs,
            )
        except httpx.TimeoutException as exc:
            raise RoutingError(
                "The routing provider timed out. Try again in a moment.",
                code="routing_timeout",
                status_code=504,
            ) from exc
        except httpx.HTTPError as exc:
            raise RoutingError(
                "The routing provider could not be reached.",
                code="routing_unavailable",
                status_code=503,
            ) from exc

        if response.status_code == 429:
            raise RoutingError(
                "The routing quota is temporarily exhausted.",
                code="routing_quota_exceeded",
                status_code=429,
            )
        if response.status_code in {400, 404}:
            raise RoutingError(
                "The requested locations could not be connected by a truck route.",
                code="route_not_found",
                status_code=422,
            )
        if response.status_code >= 500:
            raise RoutingError(
                "The routing provider is temporarily unavailable.",
                code="routing_unavailable",
                status_code=503,
            )
        if response.status_code >= 400:
            raise RoutingError(
                "The routing provider rejected the request.",
                code="routing_error",
                status_code=502,
            )
        return response.json()

    @staticmethod
    def _location_from_feature(feature: dict[str, Any]) -> Location:
        props = feature.get("properties", {})
        coordinates = feature.get("geometry", {}).get("coordinates", [0, 0])
        return Location(
            label=props.get("label") or props.get("name") or "Unknown location",
            coordinate=(float(coordinates[0]), float(coordinates[1])),
            provider_id=str(props.get("id") or props.get("gid") or props.get("osm_id") or ""),
        )
