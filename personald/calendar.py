from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import date, datetime, time
from pathlib import Path
from urllib.request import urlopen
from zoneinfo import ZoneInfo

from personald.state import DEFAULT_STATE_DIR, load_json, save_json


DEFAULT_CALENDAR_EVENTS = DEFAULT_STATE_DIR / "calendar-events.json"


@dataclass(frozen=True)
class CalendarEvent:
    id: str
    start: datetime
    end: datetime
    title: str
    type: str = "calendar"
    course: str | None = None
    location: str | None = None
    url: str | None = None
    source: str = "ics"


def import_ics(
    config: dict,
    source: str,
    name: str | None = None,
    state_path: Path = DEFAULT_CALENDAR_EVENTS,
) -> list[CalendarEvent]:
    text = _read_source(source)
    events = parse_ics(text, _timezone(config), source_name=name or Path(source).stem or "calendar")
    existing = load_calendar_events(state_path)
    merged = {event.id: event for event in existing}
    for event in events:
        merged[event.id] = event
    save_calendar_events(sorted(merged.values(), key=lambda event: (event.start, event.title)), state_path)
    return events


def load_calendar_events(state_path: Path = DEFAULT_CALENDAR_EVENTS) -> list[CalendarEvent]:
    data = load_json(state_path)
    events = data.get("events", []) if isinstance(data, dict) else []
    result: list[CalendarEvent] = []
    for raw in events:
        if not isinstance(raw, dict):
            continue
        try:
            result.append(_event_from_data(raw))
        except (KeyError, ValueError, TypeError):
            continue
    return result


def save_calendar_events(events: list[CalendarEvent], state_path: Path = DEFAULT_CALENDAR_EVENTS) -> None:
    save_json(state_path, {"events": [_event_to_data(event) for event in events]})


def calendar_events_for_day(day: date, state_path: Path = DEFAULT_CALENDAR_EVENTS) -> list[CalendarEvent]:
    events = [
        event
        for event in load_calendar_events(state_path)
        if event.start.date() <= day <= event.end.date()
    ]
    return sorted(events, key=lambda event: (event.start, event.end, event.title))


def upcoming_calendar_events(moment: datetime, days: int = 14, state_path: Path = DEFAULT_CALENDAR_EVENTS) -> list[CalendarEvent]:
    end_day = moment.date().toordinal() + days
    events = [
        event
        for event in load_calendar_events(state_path)
        if event.start >= moment and event.start.date().toordinal() <= end_day
    ]
    return sorted(events, key=lambda event: event.start)


def clear_calendar_events(state_path: Path = DEFAULT_CALENDAR_EVENTS) -> None:
    save_calendar_events([], state_path)


def parse_ics(text: str, tz: ZoneInfo, source_name: str = "calendar") -> list[CalendarEvent]:
    events: list[CalendarEvent] = []
    for raw_event in _vevent_blocks(_unfold_ics(text)):
        fields = _parse_fields(raw_event)
        start_raw = _first(fields, "DTSTART")
        end_raw = _first(fields, "DTEND")
        if not start_raw:
            continue
        start = _parse_ics_datetime(start_raw, tz)
        end = _parse_ics_datetime(end_raw, tz) if end_raw else start
        if end < start:
            end = start
        title = _clean_text(_first(fields, "SUMMARY") or "Calendar event")
        uid = _first(fields, "UID") or f"{source_name}-{start.isoformat()}-{title}"
        source_type = _classify_event(title, _first(fields, "LOCATION") or "")
        event_id = hashlib.sha1(f"{source_name}|{uid}|{start.isoformat()}".encode("utf-8")).hexdigest()[:16]
        events.append(
            CalendarEvent(
                id=event_id,
                start=start,
                end=end,
                title=title,
                type=source_type,
                course=_course_hint(title),
                location=_clean_text(_first(fields, "LOCATION")) if _first(fields, "LOCATION") else None,
                url=_first(fields, "URL"),
                source=source_name,
            )
        )
    return events


def _read_source(source: str) -> str:
    if source.startswith("http://") or source.startswith("https://"):
        with urlopen(source, timeout=15) as response:
            return response.read().decode("utf-8", errors="replace")
    return Path(source).expanduser().read_text(encoding="utf-8")


def _timezone(config: dict) -> ZoneInfo:
    return ZoneInfo(str(config.get("timezone", "UTC")))


def _unfold_ics(text: str) -> list[str]:
    lines: list[str] = []
    for raw_line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if raw_line.startswith((" ", "\t")) and lines:
            lines[-1] += raw_line[1:]
        else:
            lines.append(raw_line)
    return lines


def _vevent_blocks(lines: list[str]) -> list[list[str]]:
    blocks: list[list[str]] = []
    current: list[str] | None = None
    for line in lines:
        if line == "BEGIN:VEVENT":
            current = []
        elif line == "END:VEVENT" and current is not None:
            blocks.append(current)
            current = None
        elif current is not None:
            current.append(line)
    return blocks


def _parse_fields(lines: list[str]) -> dict[str, list[str]]:
    fields: dict[str, list[str]] = {}
    for line in lines:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        name = key.split(";", 1)[0].upper()
        fields.setdefault(name, []).append(value)
    return fields


def _first(fields: dict[str, list[str]], key: str) -> str | None:
    values = fields.get(key)
    return values[0] if values else None


def _parse_ics_datetime(value: str, tz: ZoneInfo) -> datetime:
    if re.fullmatch(r"\d{8}", value):
        return datetime.combine(datetime.strptime(value, "%Y%m%d").date(), time.min, tzinfo=tz)
    if value.endswith("Z"):
        return datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=ZoneInfo("UTC")).astimezone(tz)
    return datetime.strptime(value, "%Y%m%dT%H%M%S").replace(tzinfo=tz)


def _clean_text(value: str | None) -> str:
    if value is None:
        return ""
    return (
        value.replace("\\n", " ")
        .replace("\\,", ",")
        .replace("\\;", ";")
        .replace("\\\\", "\\")
        .strip()
    )


def _classify_event(title: str, location: str) -> str:
    text = f"{title} {location}".lower()
    if any(token in text for token in ("class", "lecture", "seminar", "lesson")):
        return "class"
    if any(token in text for token in ("meet", "zoom", "teams", "standup", "sync")):
        return "meeting"
    if any(token in text for token in ("study", "reading", "assignment")):
        return "study"
    return "calendar"


def _course_hint(title: str) -> str | None:
    match = re.search(r"\b([A-Z]{2,5}\s?\d{3,4})\b", title)
    return match.group(1) if match else None


def _event_to_data(event: CalendarEvent) -> dict:
    return {
        "id": event.id,
        "start": event.start.isoformat(),
        "end": event.end.isoformat(),
        "title": event.title,
        "type": event.type,
        "course": event.course,
        "location": event.location,
        "url": event.url,
        "source": event.source,
    }


def _event_from_data(data: dict) -> CalendarEvent:
    return CalendarEvent(
        id=str(data["id"]),
        start=datetime.fromisoformat(str(data["start"])),
        end=datetime.fromisoformat(str(data["end"])),
        title=str(data["title"]),
        type=str(data.get("type", "calendar")),
        course=data.get("course"),
        location=data.get("location"),
        url=data.get("url"),
        source=str(data.get("source", "ics")),
    )
