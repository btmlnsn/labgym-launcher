import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from labgym_launcher.backend import LauncherBackend
from labgym_launcher.errors import (
    AmbiguousHashError,
    ApprovalRequiredError,
    DependencyPlanError,
    InstallFailedError,
    InvalidHashError,
    InvalidSourceError,
    MissingHashError,
)
from fakes import DEMO_SHA, HOME_SHA, FakeRunner


class BackendTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = TemporaryDirectory()
        self.data_dir = Path(self.temp.name)
        self.runner = FakeRunner()
        self.launched = False
        self.backend = LauncherBackend(
            data_dir=self.data_dir,
            runner=self.runner,
            python="python",
            fetch_pypi_version=lambda: "3.0.1",
            launch_impl=self._launch,
        )
        self.home_path = self.data_dir / "worktrees" / "home"
        self.demo_path = self.data_dir / "worktrees" / "demo"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _launch(self) -> int:
        self.launched = True
        return 0

    def test_home_uses_persistent_canonical_checkout(self) -> None:
        confirmation = self.backend.prepare_home()
        self.assertEqual(confirmation.action, "home")
        self.assertEqual(confirmation.resolved, "3.0.1")
        self.assertEqual(confirmation.pypi_version, "3.0.1")
        self.assertEqual(confirmation.source_repo, "umyelab/LabGym")
        self.assertEqual(confirmation.checkout_path, str(self.home_path))
        self.assertEqual(confirmation.pip_spec, str(self.home_path))
        self.assertEqual(confirmation.commit, HOME_SHA)
        self.assertTrue(confirmation.needs_install)
        self.assertEqual(self.runner.install_calls(), [])
        self.assertEqual(self.runner.clone_destinations(), [str(self.home_path)])
        self.assertEqual(
            [call for call in self.runner.calls if call[:2] == ("git", "checkout")],
            [("git", "checkout", "--detach", "--force", HOME_SHA)],
        )

    def test_apply_without_approval_does_not_install(self) -> None:
        confirmation = self.backend.prepare_home()
        with self.assertRaises(ApprovalRequiredError):
            self.backend.apply(confirmation, approved=False)
        self.assertEqual(self.runner.install_calls(), [])
        self.assertFalse((self.data_dir / "state.json").exists())

    def test_install_failure_restores_freeze_and_does_not_launch(self) -> None:
        confirmation = self.backend.prepare_home()
        self.runner.install_code = 1
        with self.assertRaises(InstallFailedError) as raised:
            self.backend.apply(confirmation, approved=True)
        text = str(raised.exception)
        self.assertIn("Dependency installation failed", text)
        self.assertIn("Previous environment snapshot was restored", text)
        self.assertFalse(self.launched)
        self.assertFalse((self.data_dir / "state.json").exists())
        restores = [call for call in self.runner.install_calls() if "-r" in call]
        self.assertEqual(len(restores), 1)

    def test_dry_run_failure_does_not_install(self) -> None:
        self.runner.dry_run_code = 1
        with self.assertRaises(DependencyPlanError) as raised:
            self.backend.prepare_home()
        self.assertIn("Current environment was not changed", str(raised.exception))
        self.assertEqual(self.runner.install_calls(), [])

    def test_demo_defaults_to_canonical_source_and_reusable_checkout(self) -> None:
        confirmation = self.backend.prepare_demo("abc1def")
        self.assertEqual(confirmation.action, "demo")
        self.assertEqual(confirmation.requested, "abc1def")
        self.assertEqual(confirmation.resolved, DEMO_SHA)
        self.assertEqual(confirmation.source_repo, "umyelab/LabGym")
        self.assertEqual(confirmation.checkout_path, str(self.demo_path))
        self.assertEqual(confirmation.pip_spec, str(self.demo_path))
        self.assertEqual(self.runner.clone_destinations(), [str(self.demo_path)])
        rev_parse = [call for call in self.runner.calls if "rev-parse" in call][0]
        self.assertIn("abc1def^{commit}", rev_parse)
        self.assertEqual(
            [call for call in self.runner.calls if call[:2] == ("git", "checkout")],
            [("git", "checkout", "--detach", "--force", DEMO_SHA)],
        )

    def test_demo_custom_source_retargets_same_checkout(self) -> None:
        self.backend.prepare_demo("abc1def")
        self.runner.calls.clear()
        confirmation = self.backend.prepare_demo("abc1def", source_repo="alice/LabGym")
        self.assertEqual(confirmation.source_repo, "alice/LabGym")
        self.assertEqual(confirmation.checkout_path, str(self.demo_path))
        self.assertEqual(self.runner.clone_destinations(), [])
        set_urls = [call for call in self.runner.calls if "set-url" in call]
        self.assertTrue(any("https://github.com/alice/LabGym.git" in call for call in set_urls))
        self.assertFalse(any(DEMO_SHA in dest for dest in self.runner.clone_destinations()))

    def test_second_demo_commit_does_not_create_a_new_clone(self) -> None:
        self.backend.prepare_demo("abc1def")
        self.backend.prepare_demo("def1234")
        dests = self.runner.clone_destinations()
        self.assertEqual(dests, [str(self.demo_path)])
        self.assertEqual(
            [call for call in self.runner.calls if call[:2] == ("git", "checkout")],
            [
                ("git", "checkout", "--detach", "--force", DEMO_SHA),
                ("git", "checkout", "--detach", "--force", DEMO_SHA),
            ],
        )

    def test_home_and_demo_use_distinct_persistent_checkouts(self) -> None:
        home = self.backend.prepare_home()
        demo = self.backend.prepare_demo("abc1def")
        self.assertEqual(home.checkout_path, str(self.home_path))
        self.assertEqual(demo.checkout_path, str(self.demo_path))
        self.assertNotEqual(home.checkout_path, demo.checkout_path)
        self.assertEqual(
            set(self.runner.clone_destinations()),
            {str(self.home_path), str(self.demo_path)},
        )

    def test_demo_rejects_non_hash_before_git(self) -> None:
        with self.assertRaises(InvalidHashError):
            self.backend.prepare_demo("master")
        self.assertEqual(self.runner.calls, [])

    def test_demo_rejects_invalid_source_before_git(self) -> None:
        with self.assertRaises(InvalidSourceError):
            self.backend.prepare_demo("abc1def", source_repo="https://github.com/alice/LabGym")
        self.assertEqual(self.runner.calls, [])

    def test_ambiguous_hash_does_not_install(self) -> None:
        self.runner.resolve_code = 1
        self.runner.resolve_stderr = "error: short SHA1 abc1 is ambiguous\n"
        with self.assertRaises(AmbiguousHashError) as raised:
            self.backend.prepare_demo("abc1")
        self.assertIn("ambiguous", str(raised.exception).lower())
        self.assertIn("umyelab/LabGym", str(raised.exception))
        self.assertEqual(self.runner.install_calls(), [])

    def test_missing_hash_does_not_install(self) -> None:
        self.runner.resolve_code = 1
        self.runner.resolve_stderr = "fatal: Needed a single revision\n"
        with self.assertRaises(MissingHashError):
            self.backend.prepare_demo("bbbbbbbb")
        self.assertEqual(self.runner.install_calls(), [])

    def test_successful_home_apply_then_launch(self) -> None:
        confirmation = self.backend.prepare_home()
        self.backend.apply(confirmation, approved=True)
        self.backend.launch()
        self.assertTrue(self.launched)
        state = (self.data_dir / "state.json").read_text(encoding="utf-8")
        self.assertIn('"mode": "home"', state)
        self.assertIn("3.0.1", state)
        self.assertIn("umyelab/LabGym", state)
        installs = [call for call in self.runner.install_calls() if "-r" not in call]
        self.assertEqual(len(installs), 1)
        self.assertIn(str(self.home_path), installs[0])

    def test_status_reports_rollback_and_checkouts(self) -> None:
        status = self.backend.status()
        self.assertTrue(status.rollback_available)
        self.assertEqual(status.installed_labgym, "3.0.0")
        self.assertEqual(status.home_checkout, str(self.home_path))
        self.assertEqual(status.demo_checkout, str(self.demo_path))

    def test_rollback_uses_home_checkout(self) -> None:
        confirmation = self.backend.prepare_rollback()
        self.assertEqual(confirmation.action, "rollback")
        self.assertEqual(confirmation.pip_spec, str(self.home_path))
        self.assertEqual(confirmation.source_repo, "umyelab/LabGym")
        self.assertEqual(confirmation.pypi_version, "3.0.1")


if __name__ == "__main__":
    unittest.main()
