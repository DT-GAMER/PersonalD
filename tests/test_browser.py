import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen

from personald.browser import start_browser_server
from personald.config import load_yaml
from personald.rules import categorize_browser
from personald.storage import connect, latest_browser_event, record_browser_event


RULES = Path(__file__).resolve().parents[1] / "config-examples" / "rules.yaml"


class BrowserTests(unittest.TestCase):
    def test_categorizes_browser_by_domain(self):
        rules = load_yaml(RULES)

        self.assertEqual(categorize_browser("https://youtube.com/watch?v=1", "Video", rules), "distracting")
        self.assertEqual(categorize_browser("https://docs.google.com/document/d/1", "MBA notes", rules), "study")
        self.assertEqual(categorize_browser("https://github.com/openai/codex", "PR", rules), "work")

    def test_records_browser_event(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "personald.sqlite"
            conn = connect(db_path)
            try:
                record_browser_event(
                    conn,
                    datetime.fromisoformat("2026-06-25 10:00:00+01:00"),
                    "https://docs.google.com",
                    "MBA notes",
                    "test",
                    "study",
                    1,
                    {"url": "https://docs.google.com"},
                )
                event = latest_browser_event(conn)
            finally:
                conn.close()

        self.assertIsNotNone(event)
        self.assertEqual(event.category, "study")

    def test_browser_server_accepts_activity(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "personald.sqlite"
            config = {"timezone": "Africa/Lagos", "browser": {"enabled": True, "port": 0}}
            server = start_browser_server(config, RULES, db_path=db_path)
            port = server.server_address[1]
            try:
                body = json.dumps({
                    "url": "https://reddit.com",
                    "title": "Reddit",
                    "browser": "test",
                    "tab_id": 1,
                }).encode("utf-8")
                request = Request(
                    f"http://127.0.0.1:{port}/browser/activity",
                    data=body,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                response = json.loads(urlopen(request, timeout=2).read().decode("utf-8"))
            finally:
                server.shutdown()
                server.server_close()

        self.assertTrue(response["ok"])
        self.assertEqual(response["category"], "distracting")


if __name__ == "__main__":
    unittest.main()
