from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Literal

from planner.route_client import Route, RouteLeg

DutyStatus = Literal["off_duty", "sleeper", "driving", "on_duty"]

DRIVE_LIMIT = 11 * 60
WINDOW_LIMIT = 14 * 60
BREAK_DRIVE_LIMIT = 8 * 60
BREAK_DURATION = 30
DAILY_RESET = 10 * 60
CYCLE_LIMIT = 70 * 60
CYCLE_RESTART = 34 * 60
FUEL_INTERVAL_MILES = 1000.0
SERVICE_DURATION = 60


@dataclass
class ScheduleEvent:
    status: DutyStatus
    reason: str
    title: str
    start: datetime
    end: datetime
    start_mile: float
    end_mile: float
    coordinate: tuple[float, float]
    location: str

    @property
    def duration_minutes(self) -> float:
        return (self.end - self.start).total_seconds() / 60

    @property
    def distance_miles(self) -> float:
        return max(0.0, self.end_mile - self.start_mile)

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "reason": self.reason,
            "title": self.title,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "duration_minutes": round(self.duration_minutes, 1),
            "start_mile": round(self.start_mile, 2),
            "end_mile": round(self.end_mile, 2),
            "distance_miles": round(self.distance_miles, 2),
            "coordinate": list(self.coordinate),
            "location": self.location,
        }


@dataclass
class SchedulerState:
    now: datetime
    cycle_minutes: float
    route_mile: float = 0
    shift_start: datetime | None = None
    shift_drive_minutes: float = 0
    drive_since_break_minutes: float = 0
    next_fuel_mile: float = FUEL_INTERVAL_MILES
    events: list[ScheduleEvent] = field(default_factory=list)
    cycle_restarts: int = 0


class HOSScheduler:
    def __init__(self, route: Route, departure_at: datetime, cycle_hours_used: float):
        self.route = route
        self.state = SchedulerState(
            now=departure_at,
            cycle_minutes=cycle_hours_used * 60,
        )

    def build(self) -> tuple[list[ScheduleEvent], dict[str, Any]]:
        if not self.route.legs:
            return [], self._summary()

        for index, leg in enumerate(self.route.legs):
            self._drive_leg(leg)
            if index == 0:
                self._service("pickup", "Pickup service", leg.end_label, SERVICE_DURATION)
            elif index == len(self.route.legs) - 1:
                self._service("dropoff", "Drop-off service", leg.end_label, SERVICE_DURATION)

        return self.state.events, self._summary()

    def _drive_leg(self, leg: RouteLeg) -> None:
        remaining_minutes = max(0.0, leg.duration_minutes)
        remaining_miles = max(0.0, leg.distance_miles)

        while remaining_minutes > 0.01 and remaining_miles > 0.001:
            self._prepare_to_drive()
            state = self.state

            if state.shift_start is None:
                state.shift_start = state.now

            window_left = WINDOW_LIMIT - (state.now - state.shift_start).total_seconds() / 60
            drive_left = DRIVE_LIMIT - state.shift_drive_minutes
            break_left = BREAK_DRIVE_LIMIT - state.drive_since_break_minutes
            cycle_left = CYCLE_LIMIT - state.cycle_minutes
            miles_per_minute = remaining_miles / remaining_minutes
            miles_to_fuel = max(0.0, state.next_fuel_mile - state.route_mile)
            fuel_left = (
                miles_to_fuel / miles_per_minute if miles_per_minute > 0 else remaining_minutes
            )

            chunk_minutes = min(
                remaining_minutes,
                window_left,
                drive_left,
                break_left,
                cycle_left,
                fuel_left,
            )

            if chunk_minutes <= 0.01:
                self._resolve_blocker()
                continue

            chunk_miles = min(remaining_miles, miles_per_minute * chunk_minutes)
            start_mile = state.route_mile
            state.route_mile += chunk_miles
            self._add_event(
                status="driving",
                reason="driving",
                title=f"Drive toward {leg.end_label}",
                duration_minutes=chunk_minutes,
                start_mile=start_mile,
                end_mile=state.route_mile,
                location=leg.end_label,
            )
            state.shift_drive_minutes += chunk_minutes
            state.drive_since_break_minutes += chunk_minutes
            state.cycle_minutes += chunk_minutes
            remaining_minutes -= chunk_minutes
            remaining_miles -= chunk_miles

            if state.route_mile + 0.01 >= state.next_fuel_mile:
                self._service(
                    "fuel",
                    "Fuel stop",
                    f"Planned fuel stop near mile {round(state.route_mile)}",
                    BREAK_DURATION,
                )
                state.next_fuel_mile += FUEL_INTERVAL_MILES

    def _prepare_to_drive(self) -> None:
        state = self.state
        if state.cycle_minutes >= CYCLE_LIMIT - 0.01:
            self._rest("cycle_restart", "34-hour cycle restart", CYCLE_RESTART, "off_duty")
            state.cycle_minutes = 0
            state.cycle_restarts += 1

    def _resolve_blocker(self) -> None:
        state = self.state
        if state.cycle_minutes >= CYCLE_LIMIT - 0.01:
            self._prepare_to_drive()
            return
        if state.shift_start is not None:
            window_used = (state.now - state.shift_start).total_seconds() / 60
            daily_limit_reached = state.shift_drive_minutes >= DRIVE_LIMIT - 0.01
            window_limit_reached = window_used >= WINDOW_LIMIT - 0.01
            if daily_limit_reached or window_limit_reached:
                self._rest("sleeper", "10-hour sleeper period", DAILY_RESET, "sleeper")
                return
        if state.drive_since_break_minutes >= BREAK_DRIVE_LIMIT - 0.01:
            self._rest("break", "30-minute rest break", BREAK_DURATION, "off_duty")
            return
        raise RuntimeError("The scheduler reached an unresolved driving constraint.")

    def _service(self, reason: str, title: str, location: str, duration_minutes: float) -> None:
        state = self.state
        if state.shift_start is None:
            state.shift_start = state.now
        self._add_event(
            status="on_duty",
            reason=reason,
            title=title,
            duration_minutes=duration_minutes,
            start_mile=state.route_mile,
            end_mile=state.route_mile,
            location=location,
        )
        state.cycle_minutes += duration_minutes
        if duration_minutes >= BREAK_DURATION:
            state.drive_since_break_minutes = 0

    def _rest(
        self,
        reason: str,
        title: str,
        duration_minutes: float,
        status: Literal["off_duty", "sleeper"],
    ) -> None:
        state = self.state
        self._add_event(
            status=status,
            reason=reason,
            title=title,
            duration_minutes=duration_minutes,
            start_mile=state.route_mile,
            end_mile=state.route_mile,
            location=f"Planned rest near mile {round(state.route_mile)}",
        )
        state.drive_since_break_minutes = 0
        if duration_minutes >= DAILY_RESET:
            state.shift_start = None
            state.shift_drive_minutes = 0

    def _add_event(
        self,
        *,
        status: DutyStatus,
        reason: str,
        title: str,
        duration_minutes: float,
        start_mile: float,
        end_mile: float,
        location: str,
    ) -> None:
        state = self.state
        start = state.now
        end = start + timedelta(minutes=duration_minutes)
        coordinate = self.route.coordinate_at_mile(end_mile)
        state.events.append(
            ScheduleEvent(
                status=status,
                reason=reason,
                title=title,
                start=start,
                end=end,
                start_mile=start_mile,
                end_mile=end_mile,
                coordinate=coordinate,
                location=location,
            )
        )
        state.now = end

    def _summary(self) -> dict[str, Any]:
        events = self.state.events
        driving_minutes = sum(
            event.duration_minutes for event in events if event.status == "driving"
        )
        on_duty_minutes = sum(
            event.duration_minutes for event in events if event.status in {"driving", "on_duty"}
        )
        rest_minutes = sum(
            event.duration_minutes for event in events if event.status in {"off_duty", "sleeper"}
        )
        return {
            "trip_start": events[0].start.isoformat() if events else self.state.now.isoformat(),
            "trip_end": events[-1].end.isoformat() if events else self.state.now.isoformat(),
            "driving_hours": round(driving_minutes / 60, 2),
            "on_duty_hours": round(on_duty_minutes / 60, 2),
            "planned_rest_hours": round(rest_minutes / 60, 2),
            "cycle_hours_at_completion": round(self.state.cycle_minutes / 60, 2),
            "cycle_restarts": self.state.cycle_restarts,
            "is_compliant": True,
        }
