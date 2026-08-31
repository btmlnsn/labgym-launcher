import io
import unittest
from unittest.mock import patch

from labgym_launcher.dispatch import HELP, main, split_cli_argv


class DispatchTests(unittest.TestCase):
    def test_default_invocation_opens_gui(self) -> None:
        seen = []

        def gui(argv=None):
            seen.append(list(argv or []))
            return 17

        code = main([], gui_main=gui, cli_main=lambda argv: 99)
        self.assertEqual(code, 17)
        self.assertEqual(seen, [[]])

    def test_explicit_cli_flag_reaches_cli_path(self) -> None:
        seen = []

        def cli(argv=None):
            seen.append(list(argv or []))
            return 3

        code = main(
            ["--cli", "status"],
            gui_main=lambda argv: 1,
            cli_main=cli,
        )
        self.assertEqual(code, 3)
        self.assertEqual(seen, [["status"]])

    def test_cli_demo_args_are_passed_through(self) -> None:
        seen = []

        def cli(argv=None):
            seen.append(list(argv or []))
            return 0

        main(
            ["--cli", "demo", "alice/LabGym", "abc1def"],
            gui_main=lambda argv: 1,
            cli_main=cli,
        )
        self.assertEqual(seen, [["demo", "alice/LabGym", "abc1def"]])

    def test_split_cli_argv(self) -> None:
        self.assertIsNone(split_cli_argv([]))
        self.assertIsNone(split_cli_argv(["home"]))
        self.assertEqual(split_cli_argv(["--cli"]), [])
        self.assertEqual(split_cli_argv(["--cli", "home"]), ["home"])

    def test_help_does_not_open_gui(self) -> None:
        stdout = io.StringIO()
        with patch("sys.stdout", stdout):
            code = main(["--help"], gui_main=lambda argv: 1, cli_main=lambda argv: 2)
        self.assertEqual(code, 0)
        self.assertIn("starts the desktop GUI by default", stdout.getvalue())
        self.assertEqual(stdout.getvalue(), HELP)


if __name__ == "__main__":
    unittest.main()
