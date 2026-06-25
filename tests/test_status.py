import unittest
from datetime import datetime
from pathlib import Path

from personald.config import load_yaml
from personald.status import build_status


EXAMPLE = Path(__file__).resolve().parents[1] / "config-examples" / "schedule.yaml"


class StatusTests(unittest.TestCase):
    def test_status_prefers_current_plan_item(self):
        config = load_yaml(EXAMPLE)
        moment = datetime.fromisoformat("2026-06-29 19:30:00+01:00")

        status = build_status(config, moment)

        self.assertEqual(status["display"]["primary"], "Now: Strategy Class")
        self.assertEqual(status["display"]["accent"], "class")
        self.assertEqual(status["plan"]["current"]["id"], "s2")


if __name__ == "__main__":
    unittest.main()

