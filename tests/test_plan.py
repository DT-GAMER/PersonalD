import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from personald.config import load_yaml
from personald.plan import accept_plan, add_item, load_plan, mark_item, move_item, reset_plan


EXAMPLE = Path(__file__).resolve().parents[1] / "config-examples" / "schedule.yaml"


class PlanTests(unittest.TestCase):
    def test_load_plan_generates_from_schedule(self):
        config = load_yaml(EXAMPLE)
        day = datetime.fromisoformat("2026-06-29").date()

        with tempfile.TemporaryDirectory() as tmp:
            plan = load_plan(config, day, plans_dir=Path(tmp))

        self.assertFalse(plan.accepted)
        self.assertEqual([item.id for item in plan.items], ["s1", "s2", "s3"])
        self.assertEqual(plan.items[1].title, "Strategy Class")

    def test_accept_plan_persists(self):
        config = load_yaml(EXAMPLE)
        day = datetime.fromisoformat("2026-06-29").date()

        with tempfile.TemporaryDirectory() as tmp:
            plans_dir = Path(tmp)
            accept_plan(config, day, plans_dir=plans_dir)
            plan = load_plan(config, day, plans_dir=plans_dir)

        self.assertTrue(plan.accepted)

    def test_add_move_and_mark_item(self):
        config = load_yaml(EXAMPLE)
        day = datetime.fromisoformat("2026-06-29").date()
        moment = datetime.fromisoformat("2026-06-29 08:00:00+01:00")

        with tempfile.TemporaryDirectory() as tmp:
            plans_dir = Path(tmp)
            add_item(config, day, "Read Finance", "20:00", 45, "study", "MBA 702", plans_dir)
            move_item(config, day, "m1", "20:30", moment, plans_dir)
            mark_item(config, day, "m1", "done", moment, plans_dir)
            plan = load_plan(config, day, plans_dir)

        item = [item for item in plan.items if item.id == "m1"][0]
        self.assertEqual(item.start.strftime("%H:%M"), "20:30")
        self.assertEqual(item.end.strftime("%H:%M"), "21:15")
        self.assertEqual(item.status, "done")

    def test_reset_plan_discards_manual_items(self):
        config = load_yaml(EXAMPLE)
        day = datetime.fromisoformat("2026-06-29").date()

        with tempfile.TemporaryDirectory() as tmp:
            plans_dir = Path(tmp)
            add_item(config, day, "Manual", "20:00", 30, plans_dir=plans_dir)
            reset_plan(config, day, plans_dir)
            plan = load_plan(config, day, plans_dir)

        self.assertEqual([item.id for item in plan.items], ["s1", "s2", "s3"])


if __name__ == "__main__":
    unittest.main()
