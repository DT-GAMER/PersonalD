import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from personald.cli import main


EXAMPLE = Path(__file__).resolve().parents[1] / "config-examples" / "schedule.yaml"


class CliTests(unittest.TestCase):
    def test_plan_today_command_runs(self):
        output = io.StringIO()

        with redirect_stdout(output):
            code = main(["--config", str(EXAMPLE), "--at", "2026-06-29 08:30", "plan", "today"])

        self.assertEqual(code, 0)
        self.assertIn("Plan for 2026-06-29", output.getvalue())


if __name__ == "__main__":
    unittest.main()

