from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from personald.notify import Notifier, Reminder
from personald.schedule import now_in_timezone
from personald.state import DEFAULT_STATE_DIR, load_json, save_json


DEFAULT_FOCUS_STATE = DEFAULT_STATE_DIR / "focus.json"


@dataclass(frozen=True)
class FocusSession:
    status: str
    mode: str
    title: str
    course: str | None
    started_at: datetime
    ends_at: datetime
    allowed_categories: list[str]
    distracting_categories: list[str]
    drift_warning_after_minutes: int
    paused_at: datetime | None = None
    drift_since: datetime | None = None
    last_drift_warning_at: datetime | None = None

    @property
    def is_active(self) -> bool:
        return self.status == "active"

    @property
    def is_paused(self) -> bool:
        return self.status == "paused"

    def remaining_seconds(self, moment: datetime) -> int:
        if self.is_paused:
            moment = self.paused_at or moment
        return max(0, int((self.ends_at - moment).total_seconds()))


def focus_modes(config: dict) -> dict[str, dict[str, Any]]:
    raw = config.get("focus_modes", {}) or {}
    return raw if isinstance(raw, dict) else {}


def start_focus(
    config: dict,
    mode: str,
    moment: datetime | None = None,
    title: str | None = None,
    course: str | None = None,
    minutes: int | None = None,
    state_path: Path = DEFAULT_FOCUS_STATE,
) -> FocusSession:
    moment = moment or now_in_timezone(config)
    mode_config = focus_modes(config).get(mode, {}) or {}
    if not isinstance(mode_config, dict):
        mode_config = {}

    duration = minutes or _int_value(mode_config.get("duration_minutes"), 50)
    session = FocusSession(
        status="active",
        mode=mode,
        title=title or str(mode_config.get("title") or mode.replace("_", " ").title()),
        course=course,
        started_at=moment,
        ends_at=moment + timedelta(minutes=duration),
        allowed_categories=_str_list(mode_config.get("allowed_categories")),
        distracting_categories=_str_list(mode_config.get("distracting_categories")),
        drift_warning_after_minutes=_int_value(mode_config.get("drift_warning_after_minutes"), 5),
    )
    save_focus(session, state_path)
    return session


def load_focus(state_path: Path = DEFAULT_FOCUS_STATE) -> FocusSession | None:
    data = load_json(state_path)
    if not data:
        return None
    try:
        return FocusSession(
            status=str(data["status"]),
            mode=str(data["mode"]),
            title=str(data["title"]),
            course=data.get("course"),
            started_at=datetime.fromisoformat(data["started_at"]),
            ends_at=datetime.fromisoformat(data["ends_at"]),
            allowed_categories=_str_list(data.get("allowed_categories")),
            distracting_categories=_str_list(data.get("distracting_categories")),
            drift_warning_after_minutes=_int_value(data.get("drift_warning_after_minutes"), 5),
            paused_at=_optional_datetime(data.get("paused_at")),
            drift_since=_optional_datetime(data.get("drift_since")),
            last_drift_warning_at=_optional_datetime(data.get("last_drift_warning_at")),
        )
    except (KeyError, ValueError, TypeError):
        return None


def save_focus(session: FocusSession, state_path: Path = DEFAULT_FOCUS_STATE) -> None:
    save_json(
        state_path,
        {
            "status": session.status,
            "mode": session.mode,
            "title": session.title,
            "course": session.course,
            "started_at": session.started_at.isoformat(),
            "ends_at": session.ends_at.isoformat(),
            "allowed_categories": session.allowed_categories,
            "distracting_categories": session.distracting_categories,
            "drift_warning_after_minutes": session.drift_warning_after_minutes,
            "paused_at": session.paused_at.isoformat() if session.paused_at else None,
            "drift_since": session.drift_since.isoformat() if session.drift_since else None,
            "last_drift_warning_at": session.last_drift_warning_at.isoformat()
            if session.last_drift_warning_at
            else None,
        },
    )


def pause_focus(moment: datetime, state_path: Path = DEFAULT_FOCUS_STATE) -> FocusSession | None:
    session = load_focus(state_path)
    if not session or not session.is_active:
        return session
    updated = _replace(session, status="paused", paused_at=moment)
    save_focus(updated, state_path)
    return updated


def resume_focus(moment: datetime, state_path: Path = DEFAULT_FOCUS_STATE) -> FocusSession | None:
    session = load_focus(state_path)
    if not session or not session.is_paused:
        return session
    paused_at = session.paused_at or moment
    pause_duration = moment - paused_at
    updated = _replace(
        session,
        status="active",
        paused_at=None,
        ends_at=session.ends_at + pause_duration,
        drift_since=None,
        last_drift_warning_at=None,
    )
    save_focus(updated, state_path)
    return updated


def stop_focus(state_path: Path = DEFAULT_FOCUS_STATE) -> FocusSession | None:
    session = load_focus(state_path)
    if state_path.exists():
        state_path.unlink()
    return session


def check_focus(
    config: dict,
    moment: datetime,
    category: str,
    app_class: str,
    title: str,
    notifier: Notifier,
    dry_run: bool = False,
    state_path: Path = DEFAULT_FOCUS_STATE,
) -> FocusSession | None:
    session = load_focus(state_path)
    if not session:
        return None
    if session.is_paused:
        return session
    if moment >= session.ends_at:
        notifier.send(
            Reminder(
                id=f"focus-complete-{session.started_at.isoformat()}",
                when=moment,
                title=f"Focus complete: {session.title}",
                body="Take a break, stretch, hydrate, then choose the next thing.",
            )
        )
        stop_focus(state_path)
        return None

    drifting = is_drifting(session, category)
    if not drifting:
        if session.drift_since is not None:
            updated = _replace(session, drift_since=None, last_drift_warning_at=None)
            save_focus(updated, state_path)
            return updated
        return session

    drift_since = session.drift_since or moment
    warning_due = _warning_due(session, moment, drift_since)
    updated = _replace(session, drift_since=drift_since)

    if warning_due:
        notifier.send(
            Reminder(
                id=f"focus-drift-{session.started_at.isoformat()}-{moment.isoformat()}",
                when=moment,
                title=f"Still on track for {session.title}?",
                body=f"You have been in {category} for a bit: {app_class} - {title}",
            )
        )
        updated = _replace(updated, last_drift_warning_at=moment)

    save_focus(updated, state_path)
    return updated


def is_drifting(session: FocusSession, category: str) -> bool:
    if category in session.distracting_categories:
        return True
    if session.allowed_categories and category not in session.allowed_categories:
        return category not in {"unknown", "system", "idle"}
    return False


def _warning_due(session: FocusSession, moment: datetime, drift_since: datetime) -> bool:
    threshold = timedelta(minutes=session.drift_warning_after_minutes)
    if moment - drift_since < threshold:
        return False
    if session.last_drift_warning_at is None:
        return True
    return moment - session.last_drift_warning_at >= threshold


def _replace(session: FocusSession, **changes) -> FocusSession:
    data = session.__dict__.copy()
    data.update(changes)
    return FocusSession(**data)


def _int_value(value: object, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _str_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _optional_datetime(value: object) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(str(value))

