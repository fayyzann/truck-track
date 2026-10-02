from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from planner.logs import build_daily_logs
from planner.route_client import Route, RouteLeg
from planner.scheduler import HOSScheduler


def make_route(*legs: tuple[float, float]) -> Route:
    route_legs = []
    total_miles = 0.0
    total_minutes = 0.0
    for index, (miles, minutes) in enumerate(legs):
        route_legs.append(
            RouteLeg(
                distance_miles=miles,
                duration_minutes=minutes,
                start_label=f"Stop {index}",
                end_label=f"Stop {index + 1}",
            )
        )
        total_miles += miles
        total_minutes += minutes
    return Route(
        coordinates=[(-100.0, 35.0), (-90.0, 40.0)],
        distance_miles=total_miles,
        duration_minutes=total_minutes,
        legs=route_legs,
        instructions=[],
    )


def schedule(route: Route, cycle: float = 0, hour: int = 8):
    departure = datetime(2026, 1, 5, hour, tzinfo=ZoneInfo("America/Chicago"))
    return HOSScheduler(route, departure, cycle).build()


def test_short_trip_has_no_regulatory_rest():
    events, summary = schedule(make_route((100, 120), (100, 120)))

    assert [event.reason for event in events] == ["driving", "pickup", "driving", "dropoff"]
    assert summary["driving_hours"] == 4
    assert summary["cycle_restarts"] == 0


def test_eight_hours_driving_requires_break_when_no_service_occurs():
    events, _ = schedule(make_route((600, 600), (20, 20)))

    break_events = [event for event in events if event.reason == "break"]
    assert len(break_events) == 1
    assert break_events[0].duration_minutes == 30


def test_pickup_service_resets_break_clock():
    events, _ = schedule(make_route((350, 420), (350, 420)))

    assert not any(event.reason == "break" for event in events)
    assert any(event.reason == "pickup" for event in events)


def test_long_trip_requires_daily_sleeper_period():
    events, _ = schedule(make_route((300, 360), (600, 720)))

    sleepers = [event for event in events if event.reason == "sleeper"]
    assert sleepers
    assert all(event.duration_minutes == 600 for event in sleepers)


def test_fuel_is_inserted_at_thousand_miles_and_satisfies_break():
    events, _ = schedule(make_route((500, 420), (700, 588)))

    fuel = [event for event in events if event.reason == "fuel"]
    assert len(fuel) == 1
    assert fuel[0].start_mile == pytest.approx(1000, abs=0.1)
    assert fuel[0].duration_minutes == 30


def test_cycle_exhaustion_adds_conservative_restart():
    events, summary = schedule(make_route((100, 120), (100, 120)), cycle=69)

    restart = next(event for event in events if event.reason == "cycle_restart")
    assert restart.duration_minutes == 34 * 60
    assert summary["cycle_restarts"] == 1


def test_daily_logs_split_at_midnight_and_total_twenty_four_hours():
    events, _ = schedule(make_route((300, 360), (600, 720)), hour=20)
    logs = build_daily_logs(
        events,
        terminal_timezone="America/Chicago",
        origin="Dallas, TX",
        destination="Denver, CO",
        metadata={},
    )

    assert len(logs) >= 2
    for log in logs:
        assert sum(log["totals"].values()) == pytest.approx(24, abs=0.02)
        assert sum(log["display_totals"].values()) == pytest.approx(24, abs=0.02)


def test_no_driving_segment_pushes_cycle_over_seventy_hours():
    events, _ = schedule(make_route((300, 360), (300, 360)), cycle=68)
    cycle = 68 * 60
    for event in events:
        if event.reason == "cycle_restart":
            cycle = 0
        elif event.status in {"driving", "on_duty"}:
            if event.status == "driving":
                assert cycle + event.duration_minutes <= 70 * 60 + 0.01
            cycle += event.duration_minutes
