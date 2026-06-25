import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from personald.hyprland import ActiveWindow
from personald.report import build_report
from personald.storage import connect, record_activity, record_browser_event


CONFIG = {
    "timezone": "Africa/Lagos",
    "weekly_template": {
        "monday": [
            {"time": "20:00-21:00", "type": "study", "course": "MBA 701", "title": "Study"}
        ]
    },
    "study_targets": {"MBA 701": {"weekly_hours": 2}},
}


class ReportTests(unittest.TestCase):
    def test_build_report_uses_activity_and_browser_totals(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "personald.sqlite"
            conn = connect(db_path)
            try:
                window = ActiveWindow("obsidian", "MBA notes", "1", 1, {})
                record_activity(conn, datetime.fromisoformat("2026-06-22 20:00:00+01:00"), window, "study")
                record_activity(conn, datetime.fromisoformat("2026-06-22 20:30:00+01:00"), window, "study")
                record_browser_event(
                    conn,
                    datetime.fromisoformat("2026-06-22 20:05:00+01:00"),
                    "https://docs.google.com",
                    "MBA notes",
                    "test",
                    "study",
                    1,
                    {},
                )
            finally:
                conn.close()

            report = build_report(
                CONFIG,
                datetime.fromisoformat("2026-06-22").date(),
                datetime.fromisoformat("2026-06-28").date(),
                datetime.fromisoformat("2026-06-22 21:00:00+01:00"),
                db_path=db_path,
            )

        self.assertEqual(report.categories[0].category, "study")
        self.assertEqual(report.categories[0].duration_seconds, 1800)
        self.assertEqual(report.browser_categories[0].category, "study")
        self.assertEqual(report.study[0].course, "MBA 701")
        self.assertEqual(report.study[0].target_seconds, 7200)


if __name__ == "__main__":
    unittest.main()

