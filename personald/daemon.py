from __future__ import annotations

import time
from pathlib import Path

from personald.activity import capture_now, poll_seconds
from personald.browser import browser_enabled, start_browser_server
from personald.calendar import calendar_sync_enabled, calendar_sync_seconds, sync_calendar_sources
from personald.config import load_optional_yaml, load_yaml
from personald.focus import check_focus
from personald.notify import NotificationHistory, Notifier, due_reminders
from personald.schedule import now_in_timezone
from personald.storage import DEFAULT_DB, connect, record_activity
from personald.status import write_status


def run(
    config_path: Path,
    rules_path: Path,
    once: bool = False,
    dry_run: bool = False,
    db_path: Path = DEFAULT_DB,
) -> None:
    config = load_yaml(config_path.expanduser())
    rules = load_optional_yaml(rules_path.expanduser())
    history = NotificationHistory()
    notifier = Notifier(dry_run=dry_run, config=config)

    activity_enabled = _section_enabled(config, "activity")
    notifications_enabled = _section_enabled(config, "notifications")
    calendar_enabled = calendar_sync_enabled(config)
    browser_server = None
    if browser_enabled(config):
        browser_server = start_browser_server(config, rules_path, db_path=db_path, dry_run=dry_run)
        if dry_run:
            print("[browser] server listening")
    activity_interval = poll_seconds(config)
    notify_interval = _notification_poll_seconds(config)
    calendar_interval = calendar_sync_seconds(config)
    last_activity = 0.0
    last_notify = 0.0
    last_status = 0.0
    last_calendar = 0.0

    try:
        while True:
            monotonic = time.monotonic()
            moment = now_in_timezone(config)

            if activity_enabled and (last_activity == 0.0 or monotonic - last_activity >= activity_interval):
                window, category = capture_now(config, rules)
                if dry_run:
                    print(f"[activity] {category}: {window.app_class} - {window.title}")
                else:
                    conn = connect(db_path)
                    try:
                        record_activity(conn, moment, window, category)
                    finally:
                        conn.close()
                check_focus(
                    config,
                    moment,
                    category,
                    window.app_class,
                    window.title,
                    notifier,
                    dry_run=dry_run,
                )
                last_activity = monotonic

            if last_status == 0.0 or monotonic - last_status >= 2:
                if dry_run:
                    status = write_status(config, moment=moment)
                    print(f"[status] {status['display']['primary']} | {status['display']['secondary']}")
                else:
                    write_status(config, moment=moment)
                last_status = monotonic

            if notifications_enabled and (last_notify == 0.0 or monotonic - last_notify >= notify_interval):
                for reminder in due_reminders(config, moment, history):
                    notifier.send(reminder)
                    history.mark_sent(reminder)
                last_notify = monotonic

            if calendar_enabled and (last_calendar == 0.0 or monotonic - last_calendar >= calendar_interval):
                try:
                    events = sync_calendar_sources(config)
                    if dry_run:
                        print(f"[calendar] synced {len(events)} events")
                except Exception as exc:
                    if dry_run:
                        print(f"[calendar] sync failed: {exc}")
                last_calendar = monotonic

            if once:
                return

            time.sleep(1)
    except KeyboardInterrupt:
        return
    finally:
        if browser_server:
            browser_server.shutdown()
            browser_server.server_close()


def _section_enabled(config: dict, name: str) -> bool:
    raw = config.get(name, {}) or {}
    if not isinstance(raw, dict):
        return True
    return raw.get("enabled", True) is not False


def _notification_poll_seconds(config: dict) -> int:
    raw = config.get("notifications", {}) or {}
    if not isinstance(raw, dict):
        return 60
    try:
        return max(5, int(raw.get("poll_seconds", 60)))
    except (TypeError, ValueError):
        return 60
