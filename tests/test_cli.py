import io
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from labgym_launcher.backend import LauncherBackend
from labgym_launcher.cli import main
from fakes import FakeRunner


class CliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = TemporaryDirectory()
        self.runner = FakeRunner()
        self.launched = False
        self.backend = LauncherBackend(
            data_dir=Path(self.temp.name),
            runner=self.runner,
            python="python",
            fetch_pypi_version=lambda: "3.0.1",
            launch_impl=self._launch,
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _launch(self) -> int:
        self.launched = True
        return 0

    def test_status(self) -> None:
        stdout = io.StringIO()
        code = main(["status"], backend=self.backend, stdin=io.StringIO(), stdout=stdout)
        self.assertEqual(code, 0)
        text = stdout.getvalue()
        self.assertIn("Rollback to Official Release: available", text)
        self.assertIn("Official Release checkout:", text)
        self.assertIn("Selected commit checkout:", text)

    def test_home_requires_yes_before_install_and_launch(self) -> None:
        stdout = io.StringIO()
        code = main(
            ["home"],
            backend=self.backend,
            stdin=io.StringIO("yes\n"),
            stdout=stdout,
        )
        self.assertEqual(code, 0)
        self.assertIn("Proceed with installation?", stdout.getvalue())
        self.assertTrue(self.launched)
        self.assertTrue(self.runner.install_calls())

    def test_home_cancel_preserves_environment(self) -> None:
        stdout = io.StringIO()
        code = main(
            ["home"],
            backend=self.backend,
            stdin=io.StringIO("n\n"),
            stdout=stdout,
        )
        self.assertEqual(code, 0)
        self.assertIn("Current environment was not changed", stdout.getvalue())
        self.assertFalse(self.launched)
        self.assertEqual(self.runner.install_calls(), [])

    def test_demo_unresolved_hash_is_printed_and_does_not_launch(self) -> None:
        stdout = io.StringIO()
        code = main(
            ["demo", "master"],
            backend=self.backend,
            stdin=io.StringIO(),
            stdout=stdout,
        )
        self.assertEqual(code, 1)
        self.assertFalse(self.launched)
        self.assertEqual(self.runner.install_calls(), [])

    def test_demo_accepts_source_repo_and_hash(self) -> None:
        stdout = io.StringIO()
        code = main(
            ["demo", "alice/LabGym", "abc1def"],
            backend=self.backend,
            stdin=io.StringIO("y\n"),
            stdout=stdout,
        )
        self.assertEqual(code, 0)
        self.assertIn("alice/LabGym", stdout.getvalue())
        self.assertTrue(self.launched)
        demo_path = Path(self.temp.name) / "worktrees" / "demo"
        self.assertIn(str(demo_path), self.runner.clone_destinations())

    def test_rollback_does_not_launch(self) -> None:
        stdout = io.StringIO()
        code = main(
            ["rollback"],
            backend=self.backend,
            stdin=io.StringIO("y\n"),
            stdout=stdout,
        )
        self.assertEqual(code, 0)
        self.assertFalse(self.launched)
        self.assertIn("LabGym was not launched", stdout.getvalue())

    def test_repeated_official_release_skips_install_prompt(self) -> None:
        first = io.StringIO()
        code = main(
            ["home"],
            backend=self.backend,
            stdin=io.StringIO("yes\n"),
            stdout=first,
        )
        self.assertEqual(code, 0)
        self.assertIn("Proceed with installation?", first.getvalue())
        self.runner.calls.clear()
        stdout = io.StringIO()
        code = main(
            ["home"],
            backend=self.backend,
            stdin=io.StringIO(),
            stdout=stdout,
        )
        self.assertEqual(code, 0)
        text = stdout.getvalue()
        self.assertIn("The Official Release was already active", text)
        self.assertNotIn("Proceed with installation?", text)
        self.assertTrue(self.launched)
        self.assertFalse(
            any(
                call[:2] == ("git", "checkout") or "fetch" in call or "clone" in call
                for call in self.runner.calls
            )
        )

    def test_repeated_official_release_blocks_live_session(self) -> None:
        first = io.StringIO()
        code = main(
            ["home"],
            backend=self.backend,
            stdin=io.StringIO("yes\n"),
            stdout=first,
        )
        self.assertEqual(code, 0)
        live = self.backend.launch(wait=False)
        self.assertTrue(live.started)
        self.launched = False
        stdout = io.StringIO()
        code = main(
            ["home"],
            backend=self.backend,
            stdin=io.StringIO(),
            stdout=stdout,
        )
        self.assertEqual(code, 0)
        text = stdout.getvalue()
        self.assertIn("The Official Release was already active", text)
        self.assertIn("already running", text)
        self.assertIn("did not start another Official Release", text)
        self.assertFalse(self.launched)

    def test_repeated_same_commit_skips_install_prompt(self) -> None:
        first = io.StringIO()
        code = main(
            ["demo", "abc1def"],
            backend=self.backend,
            stdin=io.StringIO("y\n"),
            stdout=first,
        )
        self.assertEqual(code, 0)
        self.assertIn("Proceed with installation?", first.getvalue())
        self.runner.calls.clear()
        stdout = io.StringIO()
        code = main(
            ["demo", "abc1def"],
            backend=self.backend,
            stdin=io.StringIO(),
            stdout=stdout,
        )
        self.assertEqual(code, 0)
        text = stdout.getvalue()
        self.assertIn("The selected commit was already active", text)
        self.assertNotIn("Proceed with installation?", text)
        self.assertTrue(self.launched)


if __name__ == "__main__":
    unittest.main()
