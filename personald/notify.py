from __future__ import annotations

import subprocess
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from shutil import which

from personald.models import Deadline, ScheduleBlock
from personald.schedule import blocks_for_day, deadlines_for_range, now_in_timezone
from personald.state import DEFAULT_HISTORY, load_json, save_json


@dataclass(frozen=True)
class Reminder:
    id: str
    when: datetime
    title: str
    body: str
    urgency: str = "normal"

    def due_at(self, moment: datetime, window_seconds: int = 90) -> bool:
        if self.when > moment:
            return False
        return (moment - self.when).total_seconds() <= window_seconds


class NotificationHistory:
    def __init__(self, path: Path = DEFAULT_HISTORY):
        self.path = path
        self.data = load_json(path)
        self.sent = set(self.data.get("sent", []))

    def has_sent(self, reminder: Reminder) -> bool:
        return reminder.id in self.sent

    def mark_sent(self, reminder: Reminder) -> None:
        self.sent.add(reminder.id)
        self.data["sent"] = sorted(self.sent)
        save_json(self.path, self.data)


class Notifier:
    def __init__(self, dry_run: bool = False, config: dict | None = None):
        self.dry_run = dry_run
        self.config = config or {}

    def send(self, reminder: Reminder) -> None:
        if self.dry_run:
            print(f"[dry-run] {reminder.title}: {reminder.body}")
            if _sound_config(self.config).get("enabled", True):
                print(f"[dry-run] sound: {_sound_file(self.config)}")
            return

        subprocess.run(
            [
                "notify-send",
                "-a",
                "PersonalD",
                "-u",
                reminder.urgency,
                reminder.title,
                reminder.body,
            ],
            check=False,
        )
        play_notification_sound(self.config)


def play_notification_sound(config: dict | None = None) -> None:
    sound = _sound_config(config or {})
    if sound.get("enabled", True) is False:
        return

    repeat = _bounded_int(sound.get("repeat", 1), minimum=1, maximum=5)
    sound_file = _sound_file(config or {})
    thread = threading.Thread(
        target=_play_sound_worker,
        args=(sound_file, repeat),
        daemon=True,
    )
    thread.start()


def _play_sound_worker(sound_file: str, repeat: int) -> None:
    for _ in range(repeat):
        command = _sound_command(sound_file)
        if not command:
            return
        try:
            subprocess.run(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=8,
            )
        except (OSError, subprocess.TimeoutExpired):
            return


def _sound_command(sound_file: str) -> list[str] | None:
    path = Path(sound_file).expanduser()
    if path.is_file():
        file_arg = str(path)
        for player in ("paplay", "pw-play", "aplay"):
            if which(player):
                return [player, file_arg]
        if which("ffplay"):
            return ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", file_arg]
        if which("mpv"):
            return ["mpv", "--no-terminal", "--really-quiet", file_arg]

    if which("canberra-gtk-play"):
        return ["canberra-gtk-play", "-i", "alarm-clock-elapsed"]
    return None


def pending_reminders(config: dict, moment: datetime, lookahead_days: int = 2) -> list[Reminder]:
    reminders: list[Reminder] = []
    start_day = moment.date()

    for offset in range(lookahead_days + 1):
        for block in blocks_for_day(config, start_day + timedelta(days=offset)):
            reminders.extend(reminders_for_block(config, block))

    for deadline in deadlines_for_range(config, start_day, days=max(14, lookahead_days)):
        reminders.extend(reminders_for_deadline(config, deadline))

    return sorted(reminders, key=lambda reminder: reminder.when)


def due_reminders(config: dict, moment: datetime, history: NotificationHistory) -> list[Reminder]:
    reminders = pending_reminders(config, moment)
    return [
        reminder
        for reminder in reminders
        if reminder.due_at(moment) and not history.has_sent(reminder)
    ]


def run_notification_loop(
    config: dict,
    once: bool = False,
    dry_run: bool = False,
    history_path: Path = DEFAULT_HISTORY,
) -> None:
    notifications = _notifications_config(config)
    if notifications.get("enabled", True) is False:
        if dry_run:
            print("[dry-run] notifications disabled")
        return

    poll_seconds = int(notifications.get("poll_seconds", 60))
    history = NotificationHistory(history_path)
    notifier = Notifier(dry_run=dry_run, config=config)

    while True:
        moment = now_in_timezone(config)
        for reminder in due_reminders(config, moment, history):
            notifier.send(reminder)
            history.mark_sent(reminder)

        if once:
            return

        time.sleep(max(5, poll_seconds))


def reminders_for_block(config: dict, block: ScheduleBlock) -> list[Reminder]:
    rules = _rules_for_type(config, block.type)
    reminders: list[Reminder] = []
    before_minutes = _int_list(rules.get("before_minutes", []))

    for minutes in before_minutes:
        when = block.start - timedelta(minutes=minutes)
        reminders.append(
            Reminder(
                id=_block_id(block, f"before-{minutes}m"),
                when=when,
                title=_block_before_title(block, minutes),
                body=_block_body(block),
            )
        )

    if bool(rules.get("at_start", True)):
        reminders.append(
            Reminder(
                id=_block_id(block, "start"),
                when=block.start,
                title=_block_start_title(block),
                body=_block_body(block),
            )
        )

    return reminders


def reminders_for_deadline(config: dict, deadline: Deadline) -> list[Reminder]:
    rules = _deadline_rules(config)
    reminders: list[Reminder] = []

    for hours in _int_list(rules.get("before_hours", [24, 6, 1])):
        when = deadline.due - timedelta(hours=hours)
        reminders.append(
            Reminder(
                id=_deadline_id(deadline, f"before-{hours}h"),
                when=when,
                title=f"Deadline in {hours}h",
                body=_deadline_body(deadline),
                urgency="critical" if hours <= 6 else "normal",
            )
        )

    return reminders


def _notifications_config(config: dict) -> dict:
    raw = config.get("notifications", {}) or {}
    return raw if isinstance(raw, dict) else {}


def _sound_config(config: dict) -> dict:
    notifications = _notifications_config(config)
    raw = notifications.get("sound", {}) or {}
    return raw if isinstance(raw, dict) else {}


def _sound_file(config: dict) -> str:
    sound = _sound_config(config)
    return str(sound.get("file") or "/usr/share/sounds/freedesktop/stereo/alarm-clock-elapsed.oga")


def _bounded_int(value: object, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = minimum
    return max(minimum, min(maximum, parsed))


def _rules_for_type(config: dict, block_type: str) -> dict:
    notifications = _notifications_config(config)
    defaults = notifications.get("defaults", {}) or {}
    types = notifications.get("types", {}) or {}
    specific = types.get(block_type, {}) or {} if isinstance(types, dict) else {}

    rules = {}
    if isinstance(defaults, dict):
        rules.update(defaults)
    if isinstance(specific, dict):
        rules.update(specific)
    return rules


def _deadline_rules(config: dict) -> dict:
    notifications = _notifications_config(config)
    raw = notifications.get("deadlines", {}) or {}
    return raw if isinstance(raw, dict) else {}


def _int_list(value: object) -> list[int]:
    if value is None:
        return []
    if not isinstance(value, list):
        value = [value]

    result: list[int] = []
    for item in value:
        try:
            result.append(int(item))
        except (TypeError, ValueError):
            continue
    return result


def _block_id(block: ScheduleBlock, suffix: str) -> str:
    return "|".join(
        [
            "block",
            block.source,
            block.start.isoformat(),
            block.end.isoformat(),
            block.type,
            block.title,
            block.course or "",
            suffix,
        ]
    )


def _deadline_id(deadline: Deadline, suffix: str) -> str:
    return "|".join(
        [
            "deadline",
            deadline.due.isoformat(),
            deadline.title,
            deadline.course or "",
            suffix,
        ]
    )


def _block_before_title(block: ScheduleBlock, minutes: int) -> str:
    return f"{block.title} starts in {minutes} min"


def _block_start_title(block: ScheduleBlock) -> str:
    if block.type == "study":
        return f"Start study: {block.title}"
    if block.type == "class":
        return f"Class starting: {block.title}"
    return f"Starting now: {block.title}"


def _block_body(block: ScheduleBlock) -> str:
    course = f" [{block.course}]" if block.course else ""
    return (
        f"{block.start.strftime('%H:%M')}-{block.end.strftime('%H:%M')} "
        f"{block.type}{course}"
    )


def _deadline_body(deadline: Deadline) -> str:
    course = f" [{deadline.course}]" if deadline.course else ""
    return f"{deadline.title}{course} due {deadline.due.strftime('%Y-%m-%d %H:%M')}"
