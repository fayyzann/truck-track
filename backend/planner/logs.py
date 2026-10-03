from __future__ import annotations

from collections import defaultdict
from datetime import datetime, time, timedelta, timezone, tzinfo
from math import ceil, floor
from typing import Any
from zoneinfo import ZoneInfo

from planner.scheduler import ScheduleEvent

STATUS_ORDER = ("off_duty", "sleeper", "driving", "on_duty")


def build_daily_logs(
    events: list[ScheduleEvent],
    *,
    terminal_timezone: str,
    origin: str,
    destination: str,
    metadata: dict[str, str],
) -> list[dict[str, Any]]:
    if not events:
        return []

    terminal_zone = ZoneInfo(terminal_timezone)
    departure_offset = events[0].start.astimezone(terminal_zone).utcoffset()
    if departure_offset is None:
        raise ValueError("The terminal timezone did not provide a UTC offset.")
    # Paper logs use one home-terminal time standard for the full trip. A fixed
    # offset avoids losing or duplicating elapsed hours at DST transitions.
    zone = timezone(departure_offset, name=terminal_timezone)
    local_events = [_with_timezone(event, zone) for event in events]
    first_day = local_events[0].start.date()
    last_day = (local_events[-1].end - timedelta(microseconds=1)).date()
    logs = []
    current_day = first_day

    while current_day <= last_day:
        day_start = datetime.combine(current_day, time.min, tzinfo=zone)
        day_end = day_start + timedelta(days=1)
        segments = []
        totals: dict[str, float] = defaultdict(float)
        miles = 0.0
        remarks = []
        cursor = day_start

        for event in local_events:
            start = max(day_start, event.start)
            end = min(day_end, event.end)
            if end <= start:
                continue
            if start > cursor:
                _append_segment(segments, totals, "off_duty", cursor, start, day_start, "Off duty")

            reason = event.title
            _append_segment(segments, totals, event.status, start, end, day_start, reason)
            event_minutes = max(event.duration_minutes, 0.001)
            overlap_minutes = (end - start).total_seconds() / 60
            miles += event.distance_miles * overlap_minutes / event_minutes
            if day_start <= event.start < day_end:
                remarks.append(
                    {
                        "time": event.start.strftime("%H:%M"),
                        "text": f"{event.title} — {event.location}",
                    }
                )
            cursor = max(cursor, end)

        if cursor < day_end:
            _append_segment(segments, totals, "off_duty", cursor, day_end, day_start, "Off duty")

        total_minutes = sum(totals.values())
        if abs(total_minutes - 1440) > 0.01:
            raise RuntimeError(f"Daily log does not total 24 hours: {total_minutes} minutes")

        display_segments = _conservative_display_segments(segments)
        exact_hours = {status: totals.get(status, 0) / 60 for status in STATUS_ORDER}
        display_totals = _balanced_display_totals(exact_hours)

        logs.append(
            {
                "date": current_day.isoformat(),
                "from": origin if current_day == first_day else "En route",
                "to": destination if current_day == last_day else "En route",
                "total_miles": round(miles),
                "segments": segments,
                "totals": _balanced_display_totals(exact_hours),
                "display_segments": display_segments,
                "display_totals": {
                    status: display_totals[status] for status in STATUS_ORDER
                },
                "remarks": remarks,
                "metadata": metadata,
            }
        )
        current_day += timedelta(days=1)

    return logs


def _conservative_display_segments(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not segments:
        return []

    boundaries = [0.0]
    for index in range(len(segments) - 1):
        current = segments[index]
        following = segments[index + 1]
        minute = float(current["end_minute"])
        previous_status = current["status"]
        next_status = following["status"]

        # When a work/rest transition falls between grid marks, give the
        # quarter-hour to work. Between driving and other on-duty work, give it
        # to driving. Exact, unrounded durations remain available in `segments`.
        if next_status == "driving":
            rounded = floor(minute / 15) * 15
        elif previous_status == "driving":
            rounded = ceil(minute / 15) * 15
        elif next_status == "on_duty" and previous_status in {"off_duty", "sleeper"}:
            rounded = floor(minute / 15) * 15
        elif previous_status == "on_duty" and next_status in {"off_duty", "sleeper"}:
            rounded = ceil(minute / 15) * 15
        else:
            rounded = round(minute / 15) * 15

        boundaries.append(max(boundaries[-1], min(1440.0, float(rounded))))
    boundaries.append(1440.0)

    display: list[dict[str, Any]] = []
    for index, segment in enumerate(segments):
        start = boundaries[index]
        end = boundaries[index + 1]
        if end <= start:
            continue
        if display and display[-1]["status"] == segment["status"]:
            display[-1]["end_minute"] = end
            display[-1]["duration_minutes"] += end - start
        else:
            display.append(
                {
                    "status": segment["status"],
                    "start_minute": start,
                    "end_minute": end,
                    "duration_minutes": end - start,
                    "label": segment["label"],
                }
            )
    return display


def _balanced_display_totals(exact_hours: dict[str, float]) -> dict[str, float]:
    """Return two-decimal totals that add to 24 without rounding work downward."""
    result = {
        "driving": ceil(exact_hours.get("driving", 0) * 100 - 1e-9) / 100,
        "on_duty": ceil(exact_hours.get("on_duty", 0) * 100 - 1e-9) / 100,
        "sleeper": round(exact_hours.get("sleeper", 0), 2),
        "off_duty": round(exact_hours.get("off_duty", 0), 2),
    }
    delta = round(24 - sum(result.values()), 2)
    for status in ("off_duty", "sleeper"):
        adjusted = round(result[status] + delta, 2)
        if adjusted >= 0:
            result[status] = adjusted
            break
    return {status: result[status] for status in STATUS_ORDER}


def _with_timezone(event: ScheduleEvent, zone: tzinfo) -> ScheduleEvent:
    return ScheduleEvent(
        status=event.status,
        reason=event.reason,
        title=event.title,
        start=event.start.astimezone(zone),
        end=event.end.astimezone(zone),
        start_mile=event.start_mile,
        end_mile=event.end_mile,
        coordinate=event.coordinate,
        location=event.location,
    )


def _append_segment(
    segments: list[dict[str, Any]],
    totals: dict[str, float],
    status: str,
    start: datetime,
    end: datetime,
    day_start: datetime,
    label: str,
) -> None:
    duration = (end - start).total_seconds() / 60
    if duration <= 0:
        return
    start_minute = (start - day_start).total_seconds() / 60
    end_minute = (end - day_start).total_seconds() / 60
    continues_status = (
        segments
        and segments[-1]["status"] == status
        and abs(segments[-1]["end_minute"] - start_minute) < 0.01
    )
    if continues_status:
        segments[-1]["end_minute"] = round(end_minute, 2)
        segments[-1]["duration_minutes"] = round(
            segments[-1]["duration_minutes"] + duration, 2
        )
    else:
        segments.append(
            {
                "status": status,
                "start_minute": round(start_minute, 2),
                "end_minute": round(end_minute, 2),
                "duration_minutes": round(duration, 2),
                "label": label,
            }
        )
    totals[status] += duration
