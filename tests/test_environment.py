import unittest

from personald.environment import environment_actions, environment_names, run_environment


CONFIG = {
    "environments": {
        "mba_study": {
            "workspace": 3,
            "open": [
                {"app": "obsidian"},
                {"url": "https://docs.google.com"},
                "kitty",
            ],
        }
    }
}


class EnvironmentTests(unittest.TestCase):
    def test_environment_names(self):
        self.assertEqual(environment_names(CONFIG), ["mba_study"])

    def test_environment_actions(self):
        actions = environment_actions(CONFIG, "mba_study")

        self.assertEqual([action.kind for action in actions], ["workspace", "command", "url", "command"])
        self.assertEqual(actions[0].value, "3")
        self.assertEqual(actions[2].value, "https://docs.google.com")

    def test_run_environment_dry_run_returns_actions(self):
        actions = run_environment(CONFIG, "mba_study", dry_run=True)

        self.assertEqual(len(actions), 4)


if __name__ == "__main__":
    unittest.main()

