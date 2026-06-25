import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from personald.config import load_yaml
from personald.hyprland import ActiveWindow
from personald.rules import categorize
from personald.storage import category_totals_for_day, connect, latest_session, record_activity


RULES = Path(__file__).resolve().parents[1] / "config-examples" / "rules.yaml"


class ActivityTests(unittest.TestCase):
    def test_categorizes_by_app_class(self):
        rules = load_yaml(RULES)
        window = ActiveWindow(
            app_class="code",
            title="schedule.py - quickshell - Visual Studio Code",
            workspace="1",
            pid=123,
            raw={},
        )

        self.assertEqual(categorize(window, rules), "work")

    def test_categorizes_by_title(self):
        rules = load_yaml(RULES)
        window = ActiveWindow(
            app_class="firefox",
            title="MBA lecture notes - Google Docs",
            workspace="2",
            pid=123,
            raw={},
        )

        self.assertEqual(categorize(window, rules), "study")

    def test_records_and_merges_same_session(self):
        window = ActiveWindow(
            app_class="code",
            title="personald",
            workspace="1",
            pid=123,
            raw={"class": "code"},
        )

        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "activity.sqlite"
            conn = connect(db_path)
            try:
                record_activity(conn, datetime.fromisoformat("2026-06-24 10:00:00+01:00"), window, "work")
                record_activity(conn, datetime.fromisoformat("2026-06-24 10:05:00+01:00"), window, "work")
                session = latest_session(conn)
                totals = category_totals_for_day(conn, datetime.fromisoformat("2026-06-24").date())
            finally:
                conn.close()

        self.assertIsNotNone(session)
        self.assertEqual(session.duration_seconds, 300)
        self.assertEqual(totals[0].category, "work")
        self.assertEqual(totals[0].duration_seconds, 300)


if __name__ == "__main__":
    unittest.main()
