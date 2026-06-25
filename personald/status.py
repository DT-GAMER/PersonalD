from __future__ import annotations

from datetime import datetime
from pathlib import Path

from personald.focus import FocusSession, load_focus
from personald.plan import DailyPlan, PlanItem, load_plan
from personald.schedule import next_block, now_in_timezone
from personald.state import DEFAULT_STATE_DIR, save_json
from personald.storage import DEFAULT_DB, connect, latest_session


DEFAULT_STATUS = DEFAULT_STATE_DIR / "status.json"


def build_status(config: dict, moment: datetime | None = None) -> dict:
    moment = moment or now_in_timezone(config)
    plan = load_plan(config, moment.date())
    focus = load_focus()
    current_item = _current_plan_item(plan, moment)
    next_item = _next_plan_item(plan, moment)
    next_schedule = next_block(config, moment)
    activity = _latest_activity()

    primary = "No plan"
    secondary = "Open personalctl plan today"
    accent = "idle"

    if focus:
        primary = f"Focus: {focus.title}"
        secondary = _focus_secondary(focus, moment)
        accent = "focus" if focus.is_active else "paused"
    elif current_item:
        primary = f"Now: {current_item.title}"
        secondary = _item_time(current_item)
        accent = current_item.type
    elif next_item:
        primary = f"Next: {next_item.title}"
        secondary = _item_time(next_item)
        accent = next_item.type
    elif next_schedule:
        primary = f"Next: {next_schedule.title}"
        secondary = f"{next_schedule.start.strftime('%a %H:%M')}-{next_schedule.end.strftime('%H:%M')}"
        accent = next_schedule.type

    return {
        "updated_at": moment.isoformat(),
        "display": {
            "primary": primary,
            "secondary": secondary,
            "accent": accent,
        },
        "plan": {
            "day": plan.day.isoformat(),
            "accepted": plan.accepted,
            "current": _plan_item_data(current_item),
            "next": _plan_item_data(next_item),
        },
        "focus": _focus_data(focus, moment),
        "activity": activity,
    }


def write_status(config: dict, path: Path = DEFAULT_STATUS, moment: datetime | None = None) -> dict:
    status = build_status(config, moment)
    save_json(path, status)
    return status


def _current_plan_item(plan: DailyPlan, moment: datetime) -> PlanItem | None:
    for item in plan.items:
        if item.status == "planned" and item.is_active_at(moment):
            return item
    return None


def _next_plan_item(plan: DailyPlan, moment: datetime) -> PlanItem | None:
    upcoming = [item for item in plan.items if item.status == "planned" and item.start > moment]
    if not upcoming:
        return None
    return sorted(upcoming, key=lambda item: item.start)[0]


def _plan_item_data(item: PlanItem | None) -> dict | None:
    if item is None:
        return None
    return {
        "id": item.id,
        "title": item.title,
        "type": item.type,
        "course": item.course,
        "status": item.status,
        "start": item.start.isoformat(),
        "end": item.end.isoformat(),
    }


def _focus_data(focus: FocusSession | None, moment: datetime) -> dict | None:
    if focus is None:
        return None
    return {
        "status": focus.status,
        "mode": focus.mode,
        "title": focus.title,
        "course": focus.course,
        "remaining_seconds": focus.remaining_seconds(moment),
        "ends_at": focus.ends_at.isoformat(),
    }


def _latest_activity() -> dict | None:
    conn = connect(DEFAULT_DB)
    try:
        session = latest_session(conn)
    finally:
        conn.close()

    if session is None:
        return None
    return {
        "category": session.category,
        "app_class": session.app_class,
        "title": session.title,
        "workspace": session.workspace,
    }


def _item_time(item: PlanItem) -> str:
    if item.start == item.end:
        return item.start.strftime("%H:%M")
    return f"{item.start.strftime('%H:%M')}-{item.end.strftime('%H:%M')}"


def _focus_secondary(focus: FocusSession, moment: datetime) -> str:
    seconds = focus.remaining_seconds(moment)
    minutes = seconds // 60
    if focus.is_paused:
        return f"Paused, {minutes}m left"
    return f"{minutes}m left"

