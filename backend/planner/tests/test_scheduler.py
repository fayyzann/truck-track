import random
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


def test_fuel_is_not_added_after_trip_completion_at_exact_interval():
    events, _ = schedule(make_route((500, 300), (500, 300)))

    assert not any(event.reason == "fuel" for event in events)


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


@pytest.mark.parametrize(
    "departure",
    [
        datetime(2026, 3, 8, 7, 30, tzinfo=ZoneInfo("UTC")),
        datetime(2026, 11, 1, 6, 30, tzinfo=ZoneInfo("UTC")),
    ],
)
def test_dst_transitions_do_not_change_logged_hours_or_mileage(departure):
    route = make_route((60, 60), (60, 60))
    events, summary = HOSScheduler(route, departure, 0).build()
    logs = build_daily_logs(
        events,
        terminal_timezone="America/Chicago",
        origin="A",
        destination="C",
        metadata={},
    )

    assert summary["driving_hours"] == 2
    assert sum(event.duration_minutes for event in events if event.status == "driving") == 120
    assert sum(log["totals"]["driving"] for log in logs) == 2
    assert sum(log["total_miles"] for log in logs) == 120
    assert all(sum(log["display_totals"].values()) == 24 for log in logs)


def test_rounded_log_never_understates_driving_or_total_work():
    departure = datetime(2026, 1, 5, 8, 7, tzinfo=ZoneInfo("America/Chicago"))
    events, _ = HOSScheduler(make_route((600, 600), (20, 20)), departure, 0).build()
    logs = build_daily_logs(
        events,
        terminal_timezone="America/Chicago",
        origin="A",
        destination="C",
        metadata={},
    )

    assert next(event for event in events if event.reason == "break").duration_minutes == 30
    for log in logs:
        exact_driving = sum(
            segment["duration_minutes"]
            for segment in log["segments"]
            if segment["status"] == "driving"
        )
        display_driving = sum(
            segment["duration_minutes"]
            for segment in log["display_segments"]
            if segment["status"] == "driving"
        )
        exact_work = sum(
            segment["duration_minutes"]
            for segment in log["segments"]
            if segment["status"] in {"driving", "on_duty"}
        )
        display_work = sum(
            segment["duration_minutes"]
            for segment in log["display_segments"]
            if segment["status"] in {"driving", "on_duty"}
        )
        assert display_driving >= exact_driving
        assert display_work >= exact_work
        assert sum(segment["duration_minutes"] for segment in log["display_segments"]) == 1440
        assert round(sum(log["display_totals"].values()), 2) == 24


def test_randomized_schedules_preserve_compliance_invariants():
    generator = random.Random(20261003)

    for _ in range(250):
        route = make_route(
            (generator.uniform(1, 1_800), generator.uniform(1, 1_800)),
            (generator.uniform(1, 1_800), generator.uniform(1, 1_800)),
        )
        initial_cycle = generator.uniform(0, 70)
        departure = datetime(2026, 1, 5, 8, tzinfo=ZoneInfo("America/Chicago"))
        events, _ = HOSScheduler(route, departure, initial_cycle).build()

        cycle = initial_cycle * 60
        shift_drive = 0.0
        driving_since_break = 0.0
        shift_start = None
        for event in events:
            if event.reason == "cycle_restart":
                cycle = 0
            if event.status in {"off_duty", "sleeper"}:
                if event.duration_minutes >= 30:
                    driving_since_break = 0
                if event.duration_minutes >= 600:
                    shift_drive = 0
                    shift_start = None
                continue
            if shift_start is None:
                shift_start = event.start
            if event.status == "driving":
                assert shift_drive + event.duration_minutes <= 660.01
                assert driving_since_break + event.duration_minutes <= 480.01
                assert (event.end - shift_start).total_seconds() / 60 <= 840.01
                assert cycle + event.duration_minutes <= 4_200.01
                shift_drive += event.duration_minutes
                driving_since_break += event.duration_minutes
            elif event.duration_minutes >= 30:
                driving_since_break = 0
            cycle += event.duration_minutes

        logs = build_daily_logs(
            events,
            terminal_timezone="America/Chicago",
            origin="A",
            destination="C",
            metadata={},
        )
        for log in logs:
            exact_driving = sum(
                segment["duration_minutes"]
                for segment in log["segments"]
                if segment["status"] == "driving"
            )
            display_driving = sum(
                segment["duration_minutes"]
                for segment in log["display_segments"]
                if segment["status"] == "driving"
            )
            exact_work = sum(
                segment["duration_minutes"]
                for segment in log["segments"]
                if segment["status"] in {"driving", "on_duty"}
            )
            display_work = sum(
                segment["duration_minutes"]
                for segment in log["display_segments"]
                if segment["status"] in {"driving", "on_duty"}
            )
            assert display_driving >= exact_driving - 0.01
            assert display_work >= exact_work - 0.01
            assert round(sum(log["display_totals"].values()), 2) == 24
