import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from personald.focus import check_focus, is_drifting, load_focus, pause_focus, resume_focus, start_focus
from personald.notify import Notifier


CONFIG = {
    "timezone": "Africa/Lagos",
    "focus_modes": {
        "mba_study": {
            "title": "MBA Study",
            "duration_minutes": 50,
            "allowed_categories": ["study", "meeting"],
            "distracting_categories": ["distracting", "communication"],
            "drift_warning_after_minutes": 5,
        }
    },
}


class FocusTests(unittest.TestCase):
    def test_start_focus_uses_mode_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "focus.json"
            moment = datetime.fromisoformat("2026-06-25 20:00:00+01:00")

            session = start_focus(CONFIG, "mba_study", moment=moment, state_path=state)
            loaded = load_focus(state)

        self.assertEqual(session.title, "MBA Study")
        self.assertEqual(session.remaining_seconds(moment), 3000)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.mode, "mba_study")

    def test_pause_and_resume_extend_end_time(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "focus.json"
            start = datetime.fromisoformat("2026-06-25 20:00:00+01:00")
            start_focus(CONFIG, "mba_study", moment=start, state_path=state)

            pause_focus(start + timedelta(minutes=10), state)
            session = resume_focus(start + timedelta(minutes=20), state)

        self.assertIsNotNone(session)
        self.assertEqual(session.ends_at, start + timedelta(minutes=60))

    def test_is_drifting_checks_allowed_and_distracting_categories(self):
        with tempfile.TemporaryDirectory() as tmp:
            session = start_focus(
                CONFIG,
                "mba_study",
                moment=datetime.fromisoformat("2026-06-25 20:00:00+01:00"),
                state_path=Path(tmp) / "focus.json",
            )

        self.assertFalse(is_drifting(session, "study"))
        self.assertTrue(is_drifting(session, "distracting"))
        self.assertTrue(is_drifting(session, "work"))
        self.assertFalse(is_drifting(session, "unknown"))

    def test_check_focus_sets_drift_since_after_distraction(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "focus.json"
            start = datetime.fromisoformat("2026-06-25 20:00:00+01:00")
            start_focus(CONFIG, "mba_study", moment=start, state_path=state)

            session = check_focus(
                CONFIG,
                start + timedelta(minutes=2),
                "distracting",
                "firefox",
                "YouTube",
                Notifier(dry_run=True),
                dry_run=True,
                state_path=state,
            )

        self.assertIsNotNone(session)
        self.assertEqual(session.drift_since, start + timedelta(minutes=2))


if __name__ == "__main__":
    unittest.main()
