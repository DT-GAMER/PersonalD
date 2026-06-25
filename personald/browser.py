from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from personald.config import load_optional_yaml
from personald.focus import is_drifting, load_focus
from personald.rules import categorize_browser
from personald.schedule import now_in_timezone
from personald.storage import DEFAULT_DB, connect, latest_browser_event, record_browser_event


@dataclass(frozen=True)
class BrowserActivity:
    url: str
    title: str
    browser: str
    tab_id: int | None
    category: str


def browser_config(config: dict) -> dict:
    raw = config.get("browser", {}) or {}
    return raw if isinstance(raw, dict) else {}


def browser_enabled(config: dict) -> bool:
    return browser_config(config).get("enabled", True) is not False


def browser_port(config: dict) -> int:
    try:
        return int(browser_config(config).get("port", 47833))
    except (TypeError, ValueError):
        return 47833


def start_browser_server(config: dict, rules_path: Path, db_path: Path = DEFAULT_DB, dry_run: bool = False) -> ThreadingHTTPServer:
    rules = load_optional_yaml(rules_path.expanduser())
    port = browser_port(config)
    try:
        server = ThreadingHTTPServer(
            ("127.0.0.1", port),
            _handler_factory(config, rules, db_path, dry_run),
        )
    except OSError as exc:
        if exc.errno == 98:
            raise RuntimeError(
                f"PersonalD browser bridge port {port} is already in use. "
                "Is personald.service already running?"
            ) from exc
        raise
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def get_latest_browser(db_path: Path = DEFAULT_DB) -> BrowserActivity | None:
    conn = connect(db_path)
    try:
        event = latest_browser_event(conn)
    finally:
        conn.close()
    if not event:
        return None
    return BrowserActivity(
        url=event.url,
        title=event.title,
        browser=event.browser,
        tab_id=None,
        category=event.category,
    )


def _handler_factory(config: dict, rules: dict, db_path: Path, dry_run: bool):
    class BrowserHandler(BaseHTTPRequestHandler):
        server_version = "PersonalD-browser/0.1"

        def do_OPTIONS(self):
            self._send_json({"ok": True})

        def do_GET(self):
            if self.path == "/browser/state":
                focus = load_focus()
                self._send_json({
                    "ok": True,
                    "focus": None if focus is None else {
                        "status": focus.status,
                        "mode": focus.mode,
                        "title": focus.title,
                        "allowed_categories": focus.allowed_categories,
                        "distracting_categories": focus.distracting_categories,
                    },
                })
                return
            if self.path == "/browser/latest":
                latest = get_latest_browser(db_path)
                self._send_json({"ok": True, "latest": None if latest is None else latest.__dict__})
                return
            self._send_json({"ok": False, "error": "not found"}, status=404)

        def do_POST(self):
            if self.path != "/browser/activity":
                self._send_json({"ok": False, "error": "not found"}, status=404)
                return

            payload = self._read_json()
            url = str(payload.get("url") or "")
            title = str(payload.get("title") or "")
            browser = str(payload.get("browser") or "browser")
            tab_id = payload.get("tab_id")
            tab_id = tab_id if isinstance(tab_id, int) else None
            category = categorize_browser(url, title, rules)
            moment = now_in_timezone(config)

            if dry_run:
                print(f"[browser] {category}: {title} <{url}>")
            else:
                conn = connect(db_path)
                try:
                    record_browser_event(conn, moment, url, title, browser, category, tab_id, payload)
                finally:
                    conn.close()

            focus = load_focus()
            drifting = bool(focus and focus.is_active and is_drifting(focus, category))
            self._send_json({
                "ok": True,
                "category": category,
                "drifting": drifting,
                "message": None if not drifting else f"Still on track for {focus.title}?",
            })

        def log_message(self, format, *args):
            return

        def _read_json(self) -> dict:
            length = int(self.headers.get("Content-Length", "0") or 0)
            raw = self.rfile.read(length) if length else b"{}"
            try:
                data = json.loads(raw.decode("utf-8"))
                return data if isinstance(data, dict) else {}
            except json.JSONDecodeError:
                return {}

        def _send_json(self, data: dict, status: int = 200) -> None:
            body = json.dumps(data).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.end_headers()
            self.wfile.write(body)

    return BrowserHandler
