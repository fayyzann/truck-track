from __future__ import annotations

from dataclasses import dataclass
from math import asin, cos, isfinite, radians, sin, sqrt
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
            "/pelias/v1/search",
            params={"text": query, "size": limit},
        )
        features = data.get("features", [])
        if not isinstance(features, list):
            self._raise_invalid_response("location results")
        return [self._location_from_feature(feature) for feature in features]

    def geocode_one(self, query: str) -> Location:
        matches = self.search_locations(query, limit=5)
        if not matches:
            raise RoutingError(
                f'No routable location was found for "{query}".',
                code="location_not_found",
                status_code=422,
            )
        normalized_query = " ".join(query.casefold().split())
        exact = [
            match
            for match in matches
            if " ".join(match.label.casefold().split()) == normalized_query
        ]
        if exact:
            return exact[0]
        if len(matches) > 1:
            raise RoutingError(
                f'Multiple locations match "{query}". '
                "Choose a complete address from the suggestions.",
                code="ambiguous_location",
                status_code=422,
            )
        return matches[0]

    def reverse(self, coordinate: tuple[float, float]) -> str | None:
        try:
            data = self._request(
                "GET",
                "/pelias/v1/reverse",
                params={"point.lon": coordinate[0], "point.lat": coordinate[1], "size": 1},
                request_timeout=min(self.timeout, 5),
            )
        except RoutingError:
            return None
        features = data.get("features", [])
        if not isinstance(features, list):
            return None
        if not features:
            return None
        feature = features[0]
        if not isinstance(feature, dict):
            return None
        props = feature.get("properties", {})
        if not isinstance(props, dict):
            return None
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
        if not isinstance(features, list):
            self._raise_invalid_response("route features")
        if not features:
            raise RoutingError(
                "No truck route was returned.",
                code="route_not_found",
                status_code=422,
            )

        feature = features[0]
        if not isinstance(feature, dict):
            self._raise_invalid_response("route feature")
        properties = feature.get("properties", {})
        if not isinstance(properties, dict):
            self._raise_invalid_response("route properties")
        summary = properties.get("summary", {})
        if not isinstance(summary, dict):
            self._raise_invalid_response("route summary")
        raw_segments = properties.get("segments", [])
        if not isinstance(raw_segments, list):
            self._raise_invalid_response("route legs")
        legs: list[RouteLeg] = []
        for index, segment in enumerate(raw_segments):
            if index + 1 >= len(locations):
                break
            if not isinstance(segment, dict):
                self._raise_invalid_response("route leg")
            legs.append(
                RouteLeg(
                    distance_miles=self._provider_number(segment.get("distance"), "leg distance"),
                    duration_minutes=self._provider_number(
                        segment.get("duration"), "leg duration"
                    )
                    / 60,
                    start_label=locations[index].label,
                    end_label=locations[index + 1].label,
                )
            )

        if len(legs) != len(locations) - 1:
            raise RoutingError(
                "The routing provider returned incomplete route-leg data.",
                code="invalid_routing_response",
                status_code=502,
            )

        instructions: list[dict[str, Any]] = []
        for leg_index, segment in enumerate(raw_segments):
            steps = segment.get("steps", [])
            if not isinstance(steps, list):
                self._raise_invalid_response("route instructions")
            for step in steps:
                if not isinstance(step, dict):
                    self._raise_invalid_response("route instruction")
                instructions.append(
                    {
                        "leg_index": leg_index,
                        "instruction": step.get("instruction", "Continue"),
                        "name": step.get("name", ""),
                        "distance_miles": round(
                            self._provider_number(step.get("distance", 0), "step distance"),
                            1,
                        ),
                        "duration_minutes": round(
                            self._provider_number(step.get("duration", 0), "step duration")
                            / 60,
                            1,
                        ),
                    }
                )

        geometry = feature.get("geometry", {})
        if not isinstance(geometry, dict):
            self._raise_invalid_response("route geometry")
        raw_coordinates = geometry.get("coordinates", [])
        if not isinstance(raw_coordinates, list):
            self._raise_invalid_response("route coordinates")
        coordinates = [self._provider_coordinate(point) for point in raw_coordinates]
        distance = self._provider_number(summary.get("distance"), "route distance")
        duration_seconds = self._provider_number(summary.get("duration"), "route duration")
        if len(coordinates) < 2 or distance <= 0 or duration_seconds <= 0:
            self._raise_invalid_response("route geometry")
        return Route(
            coordinates=coordinates,
            distance_miles=distance,
            duration_minutes=duration_seconds / 60,
            legs=legs,
            instructions=instructions,
        )

    def _request(
        self, method: str, path: str, *, request_timeout: float | None = None, **kwargs
    ) -> dict[str, Any]:
        try:
            response = httpx.request(
                method,
                f"{self.base_url}{path}",
                headers={
                    **self.headers,
                    "Accept": "application/geo+json" if path.endswith("/geojson")
                    else "application/json",
                },
                timeout=request_timeout or self.timeout,
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
        if response.status_code in {401, 403}:
            raise RoutingError(
                "The routing provider credentials were rejected.",
                code="routing_auth_failed",
                status_code=502,
            )
        if response.status_code in {400, 404} and "/directions/" in path:
            provider_message = response.text.casefold()
            if "distance" in provider_message and any(
                word in provider_message for word in ("limit", "maximum", "exceed")
            ):
                raise RoutingError(
                    "The requested route exceeds the routing provider's distance limit.",
                    code="route_too_long",
                    status_code=422,
                )
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
        try:
            data = response.json()
        except ValueError as exc:
            raise RoutingError(
                "The routing provider returned an unreadable response.",
                code="invalid_routing_response",
                status_code=502,
            ) from exc
        if not isinstance(data, dict):
            raise RoutingError(
                "The routing provider returned an invalid response.",
                code="invalid_routing_response",
                status_code=502,
            )
        return data

    @staticmethod
    def _location_from_feature(feature: dict[str, Any]) -> Location:
        if not isinstance(feature, dict):
            OpenRouteServiceClient._raise_invalid_response("location result")
        props = feature.get("properties", {})
        geometry = feature.get("geometry", {})
        if not isinstance(props, dict) or not isinstance(geometry, dict):
            OpenRouteServiceClient._raise_invalid_response("location result")
        coordinates = OpenRouteServiceClient._provider_coordinate(geometry.get("coordinates"))
        return Location(
            label=str(props.get("label") or props.get("name") or "Unknown location"),
            coordinate=coordinates,
            provider_id=str(props.get("id") or props.get("gid") or props.get("osm_id") or ""),
        )

    @staticmethod
    def _provider_number(value: Any, field: str, *, allow_negative: bool = False) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise RoutingError(
                f"The routing provider returned an invalid {field}.",
                code="invalid_routing_response",
                status_code=502,
            ) from exc
        if not isfinite(number) or (number < 0 and not allow_negative):
            OpenRouteServiceClient._raise_invalid_response(field)
        return number

    @staticmethod
    def _provider_coordinate(value: Any) -> tuple[float, float]:
        if not isinstance(value, (list, tuple)) or len(value) < 2:
            OpenRouteServiceClient._raise_invalid_response("coordinate")
        longitude = OpenRouteServiceClient._provider_number(
            value[0], "longitude", allow_negative=True
        )
        latitude = OpenRouteServiceClient._provider_number(
            value[1], "latitude", allow_negative=True
        )
        if abs(longitude) > 180 or abs(latitude) > 90:
            OpenRouteServiceClient._raise_invalid_response("coordinate")
        return (longitude, latitude)

    @staticmethod
    def _raise_invalid_response(field: str) -> None:
        raise RoutingError(
            f"The routing provider returned invalid {field} data.",
            code="invalid_routing_response",
            status_code=502,
        )
