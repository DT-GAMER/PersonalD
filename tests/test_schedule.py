import unittest
from datetime import datetime
from pathlib import Path

from personald.config import load_yaml
from personald.notify import _sound_config, _sound_file, reminders_for_block, reminders_for_deadline
from personald.schedule import blocks_for_day, current_block, next_block


EXAMPLE = Path(__file__).resolve().parents[1] / "config-examples" / "schedule.yaml"


class ScheduleTests(unittest.TestCase):
    def test_blocks_for_day_include_weekly_blocks(self):
        config = load_yaml(EXAMPLE)
        blocks = blocks_for_day(config, datetime.fromisoformat("2026-06-29").date())

        self.assertEqual(
            [block.title for block in blocks],
            [
                "Software Engineering Work",
                "Strategy Class",
                "Review Strategy notes",
            ],
        )

    def test_current_block_matches_active_time(self):
        config = load_yaml(EXAMPLE)
        moment = datetime.fromisoformat("2026-06-29 19:30+01:00")

        block = current_block(config, moment)

        self.assertIsNotNone(block)
        self.assertEqual(block.title, "Strategy Class")

    def test_current_block_prefers_specific_overlap(self):
        config = {
            "timezone": "Africa/Lagos",
            "weekly_template": {
                "monday": [
                    {"time": "09:00-15:00", "type": "work", "title": "Work block"},
                    {"time": "13:00-14:00", "type": "meeting", "title": "Team meeting"},
                ]
            },
        }
        moment = datetime.fromisoformat("2026-06-29 13:30+01:00")

        block = current_block(config, moment)

        self.assertIsNotNone(block)
        self.assertEqual(block.title, "Team meeting")

    def test_current_block_allows_custom_type_priority(self):
        config = {
            "timezone": "Africa/Lagos",
            "schedule": {
                "type_priority": {
                    "study": 95,
                    "meeting": 50,
                }
            },
            "weekly_template": {
                "monday": [
                    {"time": "09:00-15:00", "type": "study", "title": "Reading block"},
                    {"time": "13:00-14:00", "type": "meeting", "title": "Optional meeting"},
                ]
            },
        }
        moment = datetime.fromisoformat("2026-06-29 13:30+01:00")

        block = current_block(config, moment)

        self.assertIsNotNone(block)
        self.assertEqual(block.title, "Reading block")

    def test_block_priority_field_overrides_type_priority(self):
        config = {
            "timezone": "Africa/Lagos",
            "weekly_template": {
                "monday": [
                    {"time": "09:00-15:00", "type": "study", "title": "Reading block", "priority": 20},
                    {"time": "13:00-14:00", "type": "meeting", "title": "Critical meeting", "priority": 100},
                ]
            },
        }
        moment = datetime.fromisoformat("2026-06-29 13:30+01:00")

        block = current_block(config, moment)

        self.assertIsNotNone(block)
        self.assertEqual(block.title, "Critical meeting")

    def test_next_block_skips_past_blocks(self):
        config = load_yaml(EXAMPLE)
        moment = datetime.fromisoformat("2026-06-29 21:05+01:00")

        block = next_block(config, moment)

        self.assertIsNotNone(block)
        self.assertEqual(block.title, "Review Strategy notes")

    def test_class_block_uses_class_reminder_rules(self):
        config = load_yaml(EXAMPLE)
        blocks = blocks_for_day(config, datetime.fromisoformat("2026-06-29").date())
        block = blocks[1]

        reminders = reminders_for_block(config, block)

        self.assertEqual(
            [reminder.title for reminder in reminders],
            [
                "Strategy Class starts in 60 min",
                "Strategy Class starts in 15 min",
                "Strategy Class starts in 5 min",
                "Class starting: Strategy Class",
            ],
        )

    def test_deadline_reminders_use_deadline_rules(self):
        config = load_yaml(EXAMPLE)
        deadline = config["deadlines"][0]
        from personald.schedule import _parse_deadline, get_timezone

        parsed = _parse_deadline(deadline, get_timezone(config))
        reminders = reminders_for_deadline(config, parsed)

        self.assertEqual([reminder.title for reminder in reminders], [
            "Deadline in 48h",
            "Deadline in 24h",
            "Deadline in 6h",
            "Deadline in 1h",
        ])

    def test_notification_sound_config_is_loaded(self):
        config = load_yaml(EXAMPLE)

        self.assertTrue(_sound_config(config)["enabled"])
        self.assertEqual(
            _sound_file(config),
            "/usr/share/sounds/freedesktop/stereo/alarm-clock-elapsed.oga",
        )


if __name__ == "__main__":
    unittest.main()
