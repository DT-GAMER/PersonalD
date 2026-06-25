from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from personald.activity import (
    capture_now,
    get_category_totals_for_day,
    get_latest,
    get_sessions_for_day,
    run_activity_loop,
)
from personald.browser import get_latest_browser
from personald.calendar import (
    CalendarEvent,
    clear_calendar_events,
    import_ics,
    calendar_events_for_day,
    sync_calendar_sources,
    upcoming_calendar_events,
)
from personald.config import DEFAULT_CONFIG, DEFAULT_RULES, ConfigError, load_optional_yaml, load_yaml
from personald.daemon import run as run_daemon
from personald.environment import (
    EnvAction,
    environment_actions,
    environment_names,
    run_cleanup,
    run_environment,
)
from personald.focus import (
    focus_modes,
    load_focus,
    pause_focus,
    resume_focus,
    start_focus,
    stop_focus,
)
from personald.models import Deadline, ScheduleBlock
from personald.notify import pending_reminders
from personald.plan import (
    DailyPlan,
    PlanItem,
    accept_plan,
    add_item,
    load_plan,
    mark_item,
    move_item,
    reset_plan,
)
from personald.report import Report, today_report, week_report
from personald.schedule import (
    blocks_for_day,
    current_block,
    deadlines_for_range,
    next_block,
    now_in_timezone,
    planned_study_minutes_this_week,
    study_targets,
)
from personald.status import build_status, write_status


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="personalctl")
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help=f"schedule config path, default: {DEFAULT_CONFIG}",
    )
    parser.add_argument(
        "--rules",
        type=Path,
        default=DEFAULT_RULES,
        help=f"activity rules path, default: {DEFAULT_RULES}",
    )
    parser.add_argument(
        "--at",
        help="override current time with ISO datetime, useful for testing",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("status", help="show what is active now and what is next")
    subparsers.add_parser("today", help="show today's schedule")
    subparsers.add_parser("next", help="show the next upcoming block")
    subparsers.add_parser("schedule", help="show the next seven days")
    subparsers.add_parser("reminders", help="preview upcoming notifications")
    daemon_parser = subparsers.add_parser("daemon", help="run the notification daemon")
    daemon_parser.add_argument("--once", action="store_true", help="check once and exit")
    daemon_parser.add_argument("--dry-run", action="store_true", help="print notifications instead of sending them")
    activity_parser = subparsers.add_parser("activity", help="inspect or track desktop activity")
    activity_subparsers = activity_parser.add_subparsers(dest="activity_command", required=True)
    activity_subparsers.add_parser("now", help="show the active Hyprland window and category")
    track_parser = activity_subparsers.add_parser("track", help="record active-window activity")
    track_parser.add_argument("--once", action="store_true", help="record one sample and exit")
    track_parser.add_argument("--dry-run", action="store_true", help="print samples instead of storing them")
    activity_subparsers.add_parser("latest", help="show the latest recorded activity session")
    activity_subparsers.add_parser("today", help="show today's recorded activity sessions")
    activity_subparsers.add_parser("summary", help="show today's category totals")
    focus_parser = subparsers.add_parser("focus", help="manage focus sessions")
    focus_subparsers = focus_parser.add_subparsers(dest="focus_command", required=True)
    focus_subparsers.add_parser("list", help="list configured focus modes")
    start_parser = focus_subparsers.add_parser("start", help="start a focus session")
    start_parser.add_argument("mode", help="focus mode name, e.g. mba_study")
    start_parser.add_argument("--minutes", type=int, help="override duration in minutes")
    start_parser.add_argument("--title", help="session title")
    start_parser.add_argument("--course", help="course name/code")
    focus_subparsers.add_parser("pause", help="pause the current focus session")
    focus_subparsers.add_parser("resume", help="resume the paused focus session")
    focus_subparsers.add_parser("stop", help="stop the current focus session")
    focus_subparsers.add_parser("status", help="show current focus status")
    plan_parser = subparsers.add_parser("plan", help="manage the editable daily plan")
    plan_subparsers = plan_parser.add_subparsers(dest="plan_command", required=True)
    plan_subparsers.add_parser("today", help="show today's generated or edited plan")
    plan_subparsers.add_parser("accept", help="accept today's plan")
    add_parser = plan_subparsers.add_parser("add", help="add a manual item to today's plan")
    add_parser.add_argument("title", help="item title")
    add_parser.add_argument("--at", dest="plan_at", required=True, help="start time, e.g. 20:00")
    add_parser.add_argument("--minutes", type=int, required=True, help="duration in minutes")
    add_parser.add_argument("--type", default="task", help="item type, default: task")
    add_parser.add_argument("--course", help="course name/code")
    done_parser = plan_subparsers.add_parser("done", help="mark an item done")
    done_parser.add_argument("item", nargs="?", default="current", help="item id or current")
    skip_parser = plan_subparsers.add_parser("skip", help="mark an item skipped")
    skip_parser.add_argument("item", nargs="?", default="current", help="item id or current")
    move_parser = plan_subparsers.add_parser("move", help="move an item to another time")
    move_parser.add_argument("item", nargs="?", default="current", help="item id or current")
    move_parser.add_argument("--to", dest="plan_to", required=True, help="new start time, e.g. 21:00")
    plan_subparsers.add_parser("reset", help="regenerate today's plan from schedule")
    ui_parser = subparsers.add_parser("ui", help="write or print Quickshell status")
    ui_subparsers = ui_parser.add_subparsers(dest="ui_command", required=True)
    ui_subparsers.add_parser("status", help="print current UI status JSON")
    ui_subparsers.add_parser("write-status", help="write current UI status JSON")
    browser_parser = subparsers.add_parser("browser", help="inspect browser bridge data")
    browser_subparsers = browser_parser.add_subparsers(dest="browser_command", required=True)
    browser_subparsers.add_parser("latest", help="show latest browser activity")
    calendar_parser = subparsers.add_parser("calendar", help="import and inspect calendar events")
    calendar_subparsers = calendar_parser.add_subparsers(dest="calendar_command", required=True)
    import_parser = calendar_subparsers.add_parser("import", help="import an .ics file or URL")
    import_parser.add_argument("source", help=".ics file path or URL")
    import_parser.add_argument("--name", help="source name, e.g. school")
    calendar_subparsers.add_parser("today", help="show imported calendar events for today")
    calendar_subparsers.add_parser("upcoming", help="show upcoming imported calendar events")
    calendar_subparsers.add_parser("sync", help="sync configured calendar .ics sources")
    calendar_subparsers.add_parser("clear", help="clear imported calendar events")
    env_parser = subparsers.add_parser("env", help="start configured app/URL environments")
    env_subparsers = env_parser.add_subparsers(dest="env_command", required=True)
    env_subparsers.add_parser("list", help="list configured environments")
    env_show = env_subparsers.add_parser("show", help="show environment actions")
    env_show.add_argument("name")
    env_start = env_subparsers.add_parser("start", help="open an environment")
    env_start.add_argument("name")
    env_start.add_argument("--dry-run", action="store_true")
    env_start.add_argument("--focus", help="start a focus mode after opening the environment")
    env_start.add_argument("--minutes", type=int, help="focus duration override")
    env_cleanup = env_subparsers.add_parser("cleanup", help="run environment cleanup actions")
    env_cleanup.add_argument("name")
    env_cleanup.add_argument("--dry-run", action="store_true")
    report_parser = subparsers.add_parser("report", help="show productivity reports")
    report_subparsers = report_parser.add_subparsers(dest="report_command", required=True)
    report_subparsers.add_parser("today", help="show today's report")
    report_subparsers.add_parser("week", help="show this week's report")

    args = parser.parse_args(argv)

    try:
        config = load_yaml(args.config.expanduser())
        moment = _resolve_moment(config, args.at)

        if args.command == "status":
            print_status(config, moment)
        elif args.command == "today":
            print_day(config, moment)
        elif args.command == "next":
            print_next(config, moment)
        elif args.command == "schedule":
            print_schedule(config, moment)
        elif args.command == "reminders":
            print_reminders(config, moment)
        elif args.command == "daemon":
            if args.at:
                raise ConfigError("--at is not supported with daemon; use reminders to preview times.")
            run_daemon(
                config_path=args.config,
                rules_path=args.rules,
                once=args.once,
                dry_run=args.dry_run,
            )
        elif args.command == "activity":
            handle_activity_command(config, args, moment)
        elif args.command == "focus":
            handle_focus_command(config, args, moment)
        elif args.command == "plan":
            handle_plan_command(config, args, moment)
        elif args.command == "ui":
            handle_ui_command(config, args, moment)
        elif args.command == "browser":
            handle_browser_command(args)
        elif args.command == "calendar":
            handle_calendar_command(config, args, moment)
        elif args.command == "env":
            handle_env_command(config, args)
        elif args.command == "report":
            handle_report_command(config, args, moment)
        else:
            parser.error(f"Unknown command: {args.command}")
    except ConfigError as exc:
        print(f"personalctl: {exc}", file=sys.stderr)
        return 2

    return 0


def print_status(config: dict, moment: datetime) -> None:
    active = current_block(config, moment)
    upcoming = next_block(config, moment)

    print(f"Now: {_format_moment(moment)}")
    if active:
        print(f"Current: {_format_block(active)}")
    else:
        print("Current: free / unscheduled")

    if upcoming:
        print(f"Next: {_format_block(upcoming)}")
    else:
        print("Next: nothing scheduled in the next 14 days")

    targets = study_targets(config)
    planned = planned_study_minutes_this_week(config, moment)
    if targets:
        print("")
        print("Study targets this week:")
        for course, target_hours in sorted(targets.items()):
            planned_hours = planned.get(course, 0) / 60
            print(f"  {course}: planned {_format_hours(planned_hours)} / target {_format_hours(target_hours)}")


def print_day(config: dict, moment: datetime) -> None:
    print(f"Today: {moment.strftime('%A, %Y-%m-%d')}")
    blocks = blocks_for_day(config, moment.date())
    if not blocks:
        print("  No scheduled blocks.")
    for block in blocks:
        marker = "now" if block.is_active_at(moment) else "   "
        print(f"  {marker} {_format_block(block)}")

    deadlines = deadlines_for_range(config, moment.date(), days=2)
    if deadlines:
        print("")
        print("Upcoming deadlines:")
        for deadline in deadlines:
            print(f"  {_format_deadline(deadline)}")


def print_next(config: dict, moment: datetime) -> None:
    upcoming = next_block(config, moment)
    if upcoming:
        print(_format_block(upcoming))
    else:
        print("No upcoming block in the next 14 days.")


def print_schedule(config: dict, moment: datetime) -> None:
    for offset in range(7):
        day_moment = moment.date().fromordinal(moment.date().toordinal() + offset)
        print(day_moment.strftime("%A, %Y-%m-%d"))
        blocks = blocks_for_day(config, day_moment)
        if not blocks:
            print("  No scheduled blocks.")
        for block in blocks:
            print(f"  {_format_block(block)}")
        if offset != 6:
            print("")


def print_reminders(config: dict, moment: datetime) -> None:
    reminders = [reminder for reminder in pending_reminders(config, moment) if reminder.when >= moment]
    if not reminders:
        print("No upcoming reminders.")
        return

    print("Upcoming reminders:")
    for reminder in reminders[:30]:
        print(f"  {reminder.when.strftime('%Y-%m-%d %H:%M')}  {reminder.title}")
        print(f"    {reminder.body}")


def handle_activity_command(config: dict, args: argparse.Namespace, moment: datetime) -> None:
    if args.activity_command == "now":
        rules = load_optional_yaml(args.rules.expanduser())
        window, category = capture_now(config, rules)
        print(f"Category: {category}")
        print(f"App: {window.app_class or '(none)'}")
        print(f"Title: {window.title or '(none)'}")
        print(f"Workspace: {window.workspace or '(unknown)'}")
        if window.pid is not None:
            print(f"PID: {window.pid}")
    elif args.activity_command == "track":
        if args.at:
            raise ConfigError("--at is not supported with activity track.")
        run_activity_loop(
            config,
            rules_path=args.rules,
            once=args.once,
            dry_run=args.dry_run,
        )
    elif args.activity_command == "latest":
        session = get_latest()
        if session is None:
            print("No activity recorded yet.")
        else:
            print(_format_activity_session(session))
    elif args.activity_command == "today":
        sessions = get_sessions_for_day(moment.date())
        if not sessions:
            print("No activity recorded today.")
        for session in sessions[-30:]:
            print(_format_activity_session(session))
    elif args.activity_command == "summary":
        totals = get_category_totals_for_day(moment.date())
        if not totals:
            print("No activity recorded today.")
        for total in totals:
            print(f"{total.category}: {_format_duration(total.duration_seconds)}")


def handle_focus_command(config: dict, args: argparse.Namespace, moment: datetime) -> None:
    if args.focus_command == "list":
        modes = focus_modes(config)
        if not modes:
            print("No focus modes configured.")
            return
        for name, raw in sorted(modes.items()):
            title = raw.get("title", name) if isinstance(raw, dict) else name
            duration = raw.get("duration_minutes", "?") if isinstance(raw, dict) else "?"
            print(f"{name}: {title} ({duration} min)")
    elif args.focus_command == "start":
        session = start_focus(
            config,
            mode=args.mode,
            moment=moment,
            title=args.title,
            course=args.course,
            minutes=args.minutes,
        )
        print(f"Started: {_format_focus_session(session, moment)}")
    elif args.focus_command == "pause":
        session = pause_focus(moment)
        print(_focus_result("Paused", session, moment))
    elif args.focus_command == "resume":
        session = resume_focus(moment)
        print(_focus_result("Resumed", session, moment))
    elif args.focus_command == "stop":
        session = stop_focus()
        if session:
            print(f"Stopped: {session.title}")
        else:
            print("No focus session running.")
    elif args.focus_command == "status":
        session = load_focus()
        if session:
            print(_format_focus_session(session, moment))
        else:
            print("No focus session running.")


def handle_plan_command(config: dict, args: argparse.Namespace, moment: datetime) -> None:
    try:
        if args.plan_command == "today":
            print_plan(load_plan(config, moment.date()), moment)
        elif args.plan_command == "accept":
            print_plan(accept_plan(config, moment.date()), moment)
        elif args.plan_command == "add":
            print_plan(
                add_item(
                    config,
                    moment.date(),
                    title=args.title,
                    start_time=args.plan_at,
                    minutes=args.minutes,
                    item_type=args.type,
                    course=args.course,
                ),
                moment,
            )
        elif args.plan_command == "done":
            print_plan(mark_item(config, moment.date(), args.item, "done", moment), moment)
        elif args.plan_command == "skip":
            print_plan(mark_item(config, moment.date(), args.item, "skipped", moment), moment)
        elif args.plan_command == "move":
            print_plan(move_item(config, moment.date(), args.item, args.plan_to, moment), moment)
        elif args.plan_command == "reset":
            print_plan(reset_plan(config, moment.date()), moment)
    except ValueError as exc:
        raise ConfigError(str(exc)) from exc


def print_plan(plan: DailyPlan, moment: datetime) -> None:
    status = "accepted" if plan.accepted else "draft"
    print(f"Plan for {plan.day.isoformat()} ({status})")
    if not plan.items:
        print("  No plan items.")
        return

    for item in plan.items:
        marker = "now" if item.is_active_at(moment) else "   "
        print(f"  {marker} {_format_plan_item(item)}")


def handle_ui_command(config: dict, args: argparse.Namespace, moment: datetime) -> None:
    import json

    if args.ui_command == "status":
        print(json.dumps(build_status(config, moment), indent=2, sort_keys=True))
    elif args.ui_command == "write-status":
        status = write_status(config, moment=moment)
        print(status["display"]["primary"])


def handle_browser_command(args: argparse.Namespace) -> None:
    if args.browser_command == "latest":
        latest = get_latest_browser()
        if latest is None:
            print("No browser activity recorded yet.")
            return
        print(f"{latest.category}: {latest.title}")
        print(latest.url)


def handle_calendar_command(config: dict, args: argparse.Namespace, moment: datetime) -> None:
    if args.calendar_command == "import":
        events = import_ics(config, args.source, name=args.name)
        print(f"Imported {len(events)} calendar events.")
        for event in events[:10]:
            print(f"  {_format_calendar_event(event)}")
    elif args.calendar_command == "today":
        events = calendar_events_for_day(moment.date())
        if not events:
            print("No imported calendar events today.")
        for event in events:
            print(_format_calendar_event(event))
    elif args.calendar_command == "upcoming":
        events = upcoming_calendar_events(moment)
        if not events:
            print("No upcoming imported calendar events.")
        for event in events[:30]:
            print(_format_calendar_event(event))
    elif args.calendar_command == "sync":
        events = sync_calendar_sources(config)
        print(f"Synced {len(events)} calendar events.")
        for event in events[:10]:
            print(f"  {_format_calendar_event(event)}")
    elif args.calendar_command == "clear":
        clear_calendar_events()
        print("Cleared imported calendar events.")


def handle_env_command(config: dict, args: argparse.Namespace) -> None:
    try:
        if args.env_command == "list":
            names = environment_names(config)
            if not names:
                print("No environments configured.")
            for name in names:
                print(name)
        elif args.env_command == "show":
            for action in environment_actions(config, args.name):
                print(_format_env_action(action))
        elif args.env_command == "start":
            actions = run_environment(config, args.name, dry_run=args.dry_run)
            print(f"{'Would run' if args.dry_run else 'Started'} {args.name}:")
            for action in actions:
                print(f"  {_format_env_action(action)}")
            if args.focus:
                if args.dry_run:
                    print(f"  focus: {args.focus}")
                else:
                    session = start_focus(config, args.focus, minutes=args.minutes)
                    print(f"  focus: {_format_focus_session(session, now_in_timezone(config))}")
        elif args.env_command == "cleanup":
            actions = run_cleanup(config, args.name, dry_run=args.dry_run)
            print(f"{'Would cleanup' if args.dry_run else 'Cleaned up'} {args.name}:")
            if not actions:
                print("  No cleanup actions configured.")
            for action in actions:
                print(f"  {_format_env_action(action)}")
    except ValueError as exc:
        raise ConfigError(str(exc)) from exc


def handle_report_command(config: dict, args: argparse.Namespace, moment: datetime) -> None:
    if args.report_command == "today":
        print_report(today_report(config, moment))
    elif args.report_command == "week":
        print_report(week_report(config, moment))


def print_report(report: Report) -> None:
    print(f"Report: {report.start_day.isoformat()} to {report.end_day.isoformat()}")
    print("")
    print("Activity:")
    if not report.categories:
        print("  No activity recorded.")
    for total in report.categories:
        print(f"  {total.category}: {_format_duration(total.duration_seconds)}")

    print("")
    print("Browser:")
    if not report.browser_categories:
        print("  No browser activity recorded.")
    for total in report.browser_categories:
        print(f"  {total.category}: {total.count} events")

    print("")
    print("Plan:")
    print(f"  planned: {report.plan.planned}")
    print(f"  done: {report.plan.done}")
    print(f"  skipped: {report.plan.skipped}")

    if report.study:
        print("")
        print("Study:")
        for item in report.study:
            print(
                f"  {item.course}: actual {_format_duration(item.actual_seconds)}, "
                f"planned {_format_duration(item.planned_seconds)}, "
                f"target {_format_duration(item.target_seconds)}"
            )

    print("")
    print("Recommendations:")
    for recommendation in report.recommendations:
        print(f"  - {recommendation}")


def _resolve_moment(config: dict, value: str | None) -> datetime:
    if value is None:
        return now_in_timezone(config)

    tz = now_in_timezone(config).tzinfo
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ConfigError(f"Invalid --at datetime: {value}") from exc

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=tz)
    return parsed.astimezone(tz)


def _format_block(block: ScheduleBlock) -> str:
    course = f" [{block.course}]" if block.course else ""
    return (
        f"{block.start.strftime('%H:%M')}-{block.end.strftime('%H:%M')} "
        f"{block.title}{course} ({block.type})"
    )


def _format_deadline(deadline: Deadline) -> str:
    course = f" [{deadline.course}]" if deadline.course else ""
    return f"{deadline.due.strftime('%Y-%m-%d %H:%M')} {deadline.title}{course}"


def _format_moment(moment: datetime) -> str:
    return moment.strftime("%A, %Y-%m-%d %H:%M %Z")


def _format_hours(hours: float) -> str:
    if hours == int(hours):
        return f"{int(hours)}h"
    return f"{hours:.1f}h"


def _format_activity_session(session) -> str:
    end = session.ended_at.strftime("%H:%M:%S") if session.ended_at else "now"
    title = session.title or "(no title)"
    return (
        f"{session.started_at.strftime('%H:%M:%S')}-{end} "
        f"{_format_duration(session.duration_seconds)} "
        f"{session.category} {session.app_class} [{session.workspace}] - {title}"
    )


def _format_duration(seconds: int) -> str:
    seconds = max(0, int(seconds))
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def _focus_result(action: str, session, moment: datetime) -> str:
    if not session:
        return "No focus session running."
    return f"{action}: {_format_focus_session(session, moment)}"


def _format_focus_session(session, moment: datetime) -> str:
    course = f" [{session.course}]" if session.course else ""
    return (
        f"{session.status} {session.title}{course} "
        f"mode={session.mode} remaining={_format_duration(session.remaining_seconds(moment))}"
    )


def _format_plan_item(item: PlanItem) -> str:
    course = f" [{item.course}]" if item.course else ""
    if item.start == item.end:
        time_text = item.start.strftime("%H:%M")
    else:
        time_text = f"{item.start.strftime('%H:%M')}-{item.end.strftime('%H:%M')}"
    return f"{item.id} {time_text} {item.title}{course} ({item.type}, {item.status})"


def _format_calendar_event(event: CalendarEvent) -> str:
    course = f" [{event.course}]" if event.course else ""
    if event.start == event.end:
        time_text = event.start.strftime("%Y-%m-%d %H:%M")
    else:
        time_text = f"{event.start.strftime('%Y-%m-%d %H:%M')}-{event.end.strftime('%H:%M')}"
    return f"{time_text} {event.title}{course} ({event.type}, {event.source})"


def _format_env_action(action: EnvAction) -> str:
    return f"{action.kind}: {action.value}"


if __name__ == "__main__":
    raise SystemExit(main())
