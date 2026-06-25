from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, time
from pathlib import Path

from personald.hyprland import ActiveWindow


DEFAULT_DATA_DIR = Path.home() / ".local" / "share" / "personald"
DEFAULT_DB = DEFAULT_DATA_DIR / "personald.sqlite"


@dataclass(frozen=True)
class ActivitySession:
    started_at: datetime
    ended_at: datetime | None
    app_class: str
    title: str
    workspace: str
    category: str
    duration_seconds: int


@dataclass(frozen=True)
class CategoryTotal:
    category: str
    duration_seconds: int


@dataclass(frozen=True)
class BrowserEvent:
    timestamp: datetime
    url: str
    title: str
    browser: str
    category: str


@dataclass(frozen=True)
class BrowserCategoryTotal:
    category: str
    count: int


def connect(path: Path = DEFAULT_DB) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS activity_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            app_class TEXT NOT NULL,
            title TEXT NOT NULL,
            workspace TEXT NOT NULL,
            pid INTEGER,
            category TEXT NOT NULL,
            raw_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS activity_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TEXT NOT NULL,
            ended_at TEXT,
            app_class TEXT NOT NULL,
            title TEXT NOT NULL,
            workspace TEXT NOT NULL,
            category TEXT NOT NULL,
            duration_seconds INTEGER NOT NULL DEFAULT 0
        );

        CREATE INDEX IF NOT EXISTS idx_activity_events_timestamp
            ON activity_events(timestamp);

        CREATE INDEX IF NOT EXISTS idx_activity_sessions_started_at
            ON activity_sessions(started_at);

        CREATE TABLE IF NOT EXISTS browser_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            url TEXT NOT NULL,
            title TEXT NOT NULL,
            browser TEXT NOT NULL,
            category TEXT NOT NULL,
            tab_id INTEGER,
            raw_json TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_browser_events_timestamp
            ON browser_events(timestamp);
        """
    )
    conn.commit()


def record_activity(
    conn: sqlite3.Connection,
    moment: datetime,
    window: ActiveWindow,
    category: str,
) -> None:
    conn.execute(
        """
        INSERT INTO activity_events (
            timestamp, app_class, title, workspace, pid, category, raw_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            moment.isoformat(),
            window.app_class,
            window.title,
            window.workspace,
            window.pid,
            category,
            json.dumps(window.raw, sort_keys=True),
        ),
    )

    current = conn.execute(
        """
        SELECT * FROM activity_sessions
        WHERE ended_at IS NULL
        ORDER BY id DESC
        LIMIT 1
        """
    ).fetchone()

    if current and _same_session(current, window, category):
        started = datetime.fromisoformat(current["started_at"])
        conn.execute(
            """
            UPDATE activity_sessions
            SET duration_seconds = ?
            WHERE id = ?
            """,
            (max(0, int((moment - started).total_seconds())), current["id"]),
        )
    else:
        if current:
            started = datetime.fromisoformat(current["started_at"])
            duration = max(0, int((moment - started).total_seconds()))
            conn.execute(
                """
                UPDATE activity_sessions
                SET ended_at = ?, duration_seconds = ?
                WHERE id = ?
                """,
                (moment.isoformat(), duration, current["id"]),
            )

        conn.execute(
            """
            INSERT INTO activity_sessions (
                started_at, app_class, title, workspace, category, duration_seconds
            ) VALUES (?, ?, ?, ?, ?, 0)
            """,
            (
                moment.isoformat(),
                window.app_class,
                window.title,
                window.workspace,
                category,
            ),
        )

    conn.commit()


def latest_session(conn: sqlite3.Connection) -> ActivitySession | None:
    row = conn.execute(
        """
        SELECT * FROM activity_sessions
        ORDER BY id DESC
        LIMIT 1
        """
    ).fetchone()
    return _session_from_row(row) if row else None


def sessions_for_day(conn: sqlite3.Connection, day: date) -> list[ActivitySession]:
    start = datetime.combine(day, time.min).isoformat()
    end = datetime.combine(day, time.max).isoformat()
    rows = conn.execute(
        """
        SELECT * FROM activity_sessions
        WHERE started_at BETWEEN ? AND ?
        ORDER BY started_at ASC
        """,
        (start, end),
    ).fetchall()
    return [_session_from_row(row) for row in rows]


def sessions_for_range(conn: sqlite3.Connection, start_day: date, end_day: date) -> list[ActivitySession]:
    start = datetime.combine(start_day, time.min).isoformat()
    end = datetime.combine(end_day, time.max).isoformat()
    rows = conn.execute(
        """
        SELECT * FROM activity_sessions
        WHERE started_at BETWEEN ? AND ?
        ORDER BY started_at ASC
        """,
        (start, end),
    ).fetchall()
    return [_session_from_row(row) for row in rows]


def category_totals_for_day(conn: sqlite3.Connection, day: date) -> list[CategoryTotal]:
    return category_totals_for_range(conn, day, day)


def category_totals_for_range(conn: sqlite3.Connection, start_day: date, end_day: date) -> list[CategoryTotal]:
    start = datetime.combine(start_day, time.min).isoformat()
    end = datetime.combine(end_day, time.max).isoformat()
    rows = conn.execute(
        """
        SELECT category, SUM(duration_seconds) AS total
        FROM activity_sessions
        WHERE started_at BETWEEN ? AND ?
        GROUP BY category
        ORDER BY total DESC
        """,
        (start, end),
    ).fetchall()
    return [
        CategoryTotal(category=row["category"], duration_seconds=int(row["total"] or 0))
        for row in rows
    ]


def record_browser_event(
    conn: sqlite3.Connection,
    moment: datetime,
    url: str,
    title: str,
    browser: str,
    category: str,
    tab_id: int | None,
    raw: dict,
) -> None:
    conn.execute(
        """
        INSERT INTO browser_events (
            timestamp, url, title, browser, category, tab_id, raw_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            moment.isoformat(),
            url,
            title,
            browser,
            category,
            tab_id,
            json.dumps(raw, sort_keys=True),
        ),
    )
    conn.commit()


def latest_browser_event(conn: sqlite3.Connection) -> BrowserEvent | None:
    row = conn.execute(
        """
        SELECT * FROM browser_events
        ORDER BY id DESC
        LIMIT 1
        """
    ).fetchone()
    if not row:
        return None
    return BrowserEvent(
        timestamp=datetime.fromisoformat(row["timestamp"]),
        url=row["url"],
        title=row["title"],
        browser=row["browser"],
        category=row["category"],
    )


def browser_totals_for_range(conn: sqlite3.Connection, start_day: date, end_day: date) -> list[BrowserCategoryTotal]:
    start = datetime.combine(start_day, time.min).isoformat()
    end = datetime.combine(end_day, time.max).isoformat()
    rows = conn.execute(
        """
        SELECT category, COUNT(*) AS total
        FROM browser_events
        WHERE timestamp BETWEEN ? AND ?
        GROUP BY category
        ORDER BY total DESC
        """,
        (start, end),
    ).fetchall()
    return [
        BrowserCategoryTotal(category=row["category"], count=int(row["total"] or 0))
        for row in rows
    ]


def _same_session(row: sqlite3.Row, window: ActiveWindow, category: str) -> bool:
    return (
        row["app_class"] == window.app_class
        and row["title"] == window.title
        and row["workspace"] == window.workspace
        and row["category"] == category
    )


def _session_from_row(row: sqlite3.Row) -> ActivitySession:
    ended = row["ended_at"]
    return ActivitySession(
        started_at=datetime.fromisoformat(row["started_at"]),
        ended_at=datetime.fromisoformat(ended) if ended else None,
        app_class=row["app_class"],
        title=row["title"],
        workspace=row["workspace"],
        category=row["category"],
        duration_seconds=int(row["duration_seconds"]),
    )
