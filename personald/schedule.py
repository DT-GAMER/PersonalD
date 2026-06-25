from __future__ import annotations

from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from personald.config import ConfigError
from personald.calendar import calendar_events_for_day
from personald.models import Deadline, ScheduleBlock


DAY_NAMES = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)


def get_timezone(config: dict) -> ZoneInfo:
    name = config.get("timezone", "UTC")
    try:
        return ZoneInfo(str(name))
    except ZoneInfoNotFoundError as exc:
        raise ConfigError(f"Unknown timezone: {name}") from exc


def now_in_timezone(config: dict) -> datetime:
    return datetime.now(get_timezone(config))


def blocks_for_day(config: dict, day: date, calendar_state_path: Path | None = None) -> list[ScheduleBlock]:
    tz = get_timezone(config)
    blocks: list[ScheduleBlock] = []
    day_name = DAY_NAMES[day.weekday()]

    weekly = config.get("weekly_template", {})
    if weekly is None:
        weekly = {}
    if not isinstance(weekly, dict):
        raise ConfigError("weekly_template must be a mapping of day names to blocks.")

    for raw in weekly.get(day_name, []) or []:
        blocks.append(_parse_weekly_block(raw, day, tz))

    for raw in config.get("events", []) or []:
        block = _parse_event_block(raw, tz)
        if block.start.date() == day:
            blocks.append(block)

    calendar_events = calendar_events_for_day(day, calendar_state_path) if calendar_state_path else calendar_events_for_day(day)
    for event in calendar_events:
        blocks.append(
            ScheduleBlock(
                start=event.start,
                end=event.end,
                type=event.type,
                title=event.title,
                course=event.course,
                source=f"calendar:{event.source}",
            )
        )

    return sorted(blocks, key=lambda block: (block.start, block.end, block.title))


def deadlines_for_range(config: dict, start_day: date, days: int = 14) -> list[Deadline]:
    tz = get_timezone(config)
    end_day = start_day + timedelta(days=days)
    deadlines: list[Deadline] = []

    for raw in config.get("deadlines", []) or []:
        deadline = _parse_deadline(raw, tz)
        if start_day <= deadline.due.date() <= end_day:
            deadlines.append(deadline)

    return sorted(deadlines, key=lambda deadline: deadline.due)


def current_block(config: dict, moment: datetime) -> ScheduleBlock | None:
    for block in blocks_for_day(config, moment.date()):
        if block.is_active_at(moment):
            return block
    return None


def next_block(config: dict, moment: datetime, search_days: int = 14) -> ScheduleBlock | None:
    for offset in range(search_days + 1):
        day = moment.date() + timedelta(days=offset)
        for block in blocks_for_day(config, day):
            if block.start > moment:
                return block
    return None


def study_targets(config: dict) -> dict[str, float]:
    raw_targets = config.get("study_targets", {}) or {}
    if not isinstance(raw_targets, dict):
        raise ConfigError("study_targets must be a mapping.")

    targets: dict[str, float] = {}
    for course, raw in raw_targets.items():
        if not isinstance(raw, dict):
            raise ConfigError(f"study target for {course} must be a mapping.")
        hours = raw.get("weekly_hours", 0)
        try:
            targets[str(course)] = float(hours)
        except (TypeError, ValueError) as exc:
            raise ConfigError(f"weekly_hours for {course} must be a number.") from exc
    return targets


def planned_study_minutes_this_week(config: dict, moment: datetime) -> dict[str, int]:
    start = moment.date() - timedelta(days=moment.weekday())
    totals: dict[str, int] = {}

    for offset in range(7):
        for block in blocks_for_day(config, start + timedelta(days=offset)):
            if block.type != "study":
                continue
            course = block.course or "General"
            totals[course] = totals.get(course, 0) + block.duration_minutes

    return totals


def _parse_weekly_block(raw: dict, day: date, tz: ZoneInfo) -> ScheduleBlock:
    _require_mapping(raw, "weekly block")
    start_text, end_text = _split_time_range(str(raw.get("time", "")))
    start = datetime.combine(day, _parse_time(start_text), tzinfo=tz)
    end = datetime.combine(day, _parse_time(end_text), tzinfo=tz)
    if end <= start:
        end += timedelta(days=1)

    return ScheduleBlock(
        start=start,
        end=end,
        type=str(raw.get("type", "event")),
        title=str(raw.get("title", raw.get("type", "Untitled"))),
        course=_optional_str(raw.get("course")),
        source="weekly",
    )


def _parse_event_block(raw: dict, tz: ZoneInfo) -> ScheduleBlock:
    _require_mapping(raw, "event")
    start = _parse_datetime(str(raw.get("start", "")), tz)
    end = _parse_datetime(str(raw.get("end", "")), tz)
    if end <= start:
        raise ConfigError(f"Event ends before it starts: {raw}")

    return ScheduleBlock(
        start=start,
        end=end,
        type=str(raw.get("type", "event")),
        title=str(raw.get("title", raw.get("type", "Untitled"))),
        course=_optional_str(raw.get("course")),
        source="event",
    )


def _parse_deadline(raw: dict, tz: ZoneInfo) -> Deadline:
    _require_mapping(raw, "deadline")
    return Deadline(
        due=_parse_datetime(str(raw.get("due", "")), tz),
        title=str(raw.get("title", "Untitled deadline")),
        course=_optional_str(raw.get("course")),
    )


def _split_time_range(value: str) -> tuple[str, str]:
    parts = value.split("-", maxsplit=1)
    if len(parts) != 2:
        raise ConfigError(f"Expected time range like 09:00-17:00, got: {value}")
    return parts[0].strip(), parts[1].strip()


def _parse_time(value: str) -> time:
    try:
        return time.fromisoformat(value)
    except ValueError as exc:
        raise ConfigError(f"Invalid time: {value}") from exc


def _parse_datetime(value: str, tz: ZoneInfo) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ConfigError(f"Invalid datetime: {value}") from exc

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=tz)
    return parsed.astimezone(tz)


def _require_mapping(raw: object, label: str) -> None:
    if not isinstance(raw, dict):
        raise ConfigError(f"{label} must be a mapping.")


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    return str(value)
