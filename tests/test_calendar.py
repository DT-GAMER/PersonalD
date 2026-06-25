import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from personald.config import ConfigError
from personald.calendar import (
    calendar_sync_enabled,
    calendar_sync_seconds,
    calendar_sync_sources,
    import_ics,
    load_calendar_events,
    parse_ics,
    sync_calendar_sources,
)
from personald.schedule import blocks_for_day


ICS = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:strategy-1
DTSTART:20260625T190000Z
DTEND:20260625T210000Z
SUMMARY:MBA 701 Strategy Class
LOCATION:Google Meet
URL:https://meet.google.com/abc-defg-hij
END:VEVENT
BEGIN:VEVENT
UID:assignment-1
DTSTART:20260626T180000Z
DTEND:20260626T190000Z
SUMMARY:Finance assignment reading
END:VEVENT
END:VCALENDAR
"""


CONFIG = {"timezone": "Africa/Lagos"}


class CalendarTests(unittest.TestCase):
    def test_parse_ics_events(self):
        events = parse_ics(ICS, datetime.now().astimezone().tzinfo)

        self.assertEqual(len(events), 2)
        self.assertEqual(events[0].title, "MBA 701 Strategy Class")
        self.assertEqual(events[0].type, "class")
        self.assertEqual(events[0].course, "MBA 701")

    def test_import_ics_persists_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            ics_path = Path(tmp) / "school.ics"
            state_path = Path(tmp) / "calendar-events.json"
            ics_path.write_text(ICS, encoding="utf-8")

            imported = import_ics(CONFIG, str(ics_path), name="school", state_path=state_path)
            loaded = load_calendar_events(state_path)

        self.assertEqual(len(imported), 2)
        self.assertEqual(len(loaded), 2)
        self.assertEqual(loaded[0].source, "school")

    def test_schedule_blocks_include_imported_calendar(self):
        with tempfile.TemporaryDirectory() as tmp:
            ics_path = Path(tmp) / "school.ics"
            state_path = Path(tmp) / "calendar-events.json"
            ics_path.write_text(ICS, encoding="utf-8")
            import_ics(CONFIG, str(ics_path), name="school", state_path=state_path)

            blocks = blocks_for_day(CONFIG, datetime.fromisoformat("2026-06-25").date(), calendar_state_path=state_path)

        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0].title, "MBA 701 Strategy Class")
        self.assertEqual(blocks[0].source, "calendar:school")

    def test_calendar_sync_config(self):
        config = {
            "calendar": {
                "sync": {
                    "enabled": True,
                    "every_minutes": 10,
                    "sources": [
                        {"name": "google", "url": "https://example.com/basic.ics"},
                    ],
                }
            }
        }

        self.assertTrue(calendar_sync_enabled(config))
        self.assertEqual(calendar_sync_seconds(config), 600)
        self.assertEqual(
            calendar_sync_sources(config),
            [{"name": "google", "url": "https://example.com/basic.ics"}],
        )

    def test_sync_calendar_sources_imports_all_configured_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            ics_path = Path(tmp) / "school.ics"
            state_path = Path(tmp) / "calendar-events.json"
            ics_path.write_text(ICS, encoding="utf-8")
            config = {
                "timezone": "Africa/Lagos",
                "calendar": {
                    "sync": {
                        "enabled": True,
                        "sources": [{"name": "school", "url": str(ics_path)}],
                    }
                },
            }

            synced = sync_calendar_sources(config, state_path=state_path)
            loaded = load_calendar_events(state_path)

        self.assertEqual(len(synced), 2)
        self.assertEqual(len(loaded), 2)

    def test_import_ics_reports_missing_source_cleanly(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "missing.ics"

            with self.assertRaisesRegex(ConfigError, "Could not read calendar source"):
                import_ics(CONFIG, str(missing))


if __name__ == "__main__":
    unittest.main()
