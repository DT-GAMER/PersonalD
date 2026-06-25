from __future__ import annotations

import time
from pathlib import Path

from personald.config import load_optional_yaml
from personald.hyprland import ActiveWindow, get_active_window
from personald.rules import categorize
from personald.schedule import now_in_timezone
from personald.storage import DEFAULT_DB, category_totals_for_day, connect, latest_session, record_activity, sessions_for_day


def activity_config(config: dict) -> dict:
    raw = config.get("activity", {}) or {}
    return raw if isinstance(raw, dict) else {}


def poll_seconds(config: dict) -> int:
    raw = activity_config(config).get("poll_seconds", 5)
    try:
        return max(1, int(raw))
    except (TypeError, ValueError):
        return 5


def capture_now(config: dict, rules: dict) -> tuple[ActiveWindow, str]:
    window = get_active_window()
    return window, categorize(window, rules)


def record_now(config: dict, rules: dict, db_path: Path = DEFAULT_DB) -> tuple[ActiveWindow, str]:
    window, category = capture_now(config, rules)
    moment = now_in_timezone(config)
    conn = connect(db_path)
    try:
        record_activity(conn, moment, window, category)
    finally:
        conn.close()
    return window, category


def run_activity_loop(
    config: dict,
    rules_path: Path,
    once: bool = False,
    dry_run: bool = False,
    db_path: Path = DEFAULT_DB,
) -> None:
    rules = load_optional_yaml(rules_path.expanduser())
    interval = poll_seconds(config)

    while True:
        window, category = capture_now(config, rules)
        if dry_run:
            print(_format_window(window, category))
        else:
            moment = now_in_timezone(config)
            conn = connect(db_path)
            try:
                record_activity(conn, moment, window, category)
            finally:
                conn.close()

        if once:
            return
        time.sleep(interval)


def get_latest(db_path: Path = DEFAULT_DB):
    conn = connect(db_path)
    try:
        return latest_session(conn)
    finally:
        conn.close()


def get_sessions_for_day(day, db_path: Path = DEFAULT_DB):
    conn = connect(db_path)
    try:
        return sessions_for_day(conn, day)
    finally:
        conn.close()


def get_category_totals_for_day(day, db_path: Path = DEFAULT_DB):
    conn = connect(db_path)
    try:
        return category_totals_for_day(conn, day)
    finally:
        conn.close()


def _format_window(window: ActiveWindow, category: str) -> str:
    title = window.title or "(no title)"
    app = window.app_class or "(no class)"
    workspace = window.workspace or "?"
    return f"{category}: {app} on workspace {workspace} - {title}"
