import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from labgym_launcher.backend import LauncherBackend
from labgym_launcher.errors import InvalidHashError
from labgym_launcher.gui_flow import (
    ALREADY_ACTIVE,
    NEEDS_CONFIRM,
    already_active_success_message,
    apply_if_approved,
    confirmation_display,
    format_session_summary,
    prepare_demo,
    prepare_home,
    record_demo_if_needed,
    select_official_release,
    select_selected_commit,
)
from labgym_launcher.constants import HOME
from labgym_launcher.recent import set_recent_alias
from fakes import DEMO_SHA, FakeRunner


class GuiFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = TemporaryDirectory()
        self.data_dir = Path(self.temp.name)
        self.runner = FakeRunner()
        self.launched = 0
        self.backend = LauncherBackend(
            data_dir=self.data_dir,
            runner=self.runner,
            python="python",
            fetch_pypi_version=lambda: "3.0.1",
            launch_impl=self._launch,
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _launch(self) -> int:
        self.launched += 1
        return 0

    def test_confirmation_includes_commit_and_dependency_changes(self) -> None:
        confirmation = prepare_home(self.backend)
        text = confirmation_display(confirmation)
        self.assertIn("Action: Official Release", text)
        self.assertIn("Resolved: 3.0.1", text)
        self.assertIn("labgym:", text)
        self.assertIn("Install required:", text)
        self.assertEqual(self.runner.install_calls(), [])

    def test_cancel_does_not_install_or_launch(self) -> None:
        confirmation = prepare_home(self.backend)
        outcome = apply_if_approved(self.backend, confirmation, approved=False, launch=True)
        self.assertEqual(outcome, "cancelled")
        self.assertEqual(self.runner.install_calls(), [])
        self.assertEqual(self.launched, 0)
        self.assertFalse((self.data_dir / "state.json").exists())

    def test_approve_installs_and_starts_without_waiting(self) -> None:
        confirmation = prepare_home(self.backend)
        outcome = apply_if_approved(self.backend, confirmation, approved=True, launch=True)
        self.assertEqual(outcome, "applied")
        self.assertTrue(self.runner.install_calls())
        self.assertEqual(self.launched, 1)
        self.assertTrue((self.data_dir / "state.json").exists())
        summary = format_session_summary(self.backend.status())
        self.assertIn("Installed: Official Release", summary)
        self.assertIn("Official Release session: running", summary)
        self.assertIn("Selected Commit session: not running", summary)
        self.assertEqual(len(summary.splitlines()), 4)

    def test_invalid_hash_does_not_install(self) -> None:
        with self.assertRaises(InvalidHashError):
            prepare_demo(self.backend, "master")
        self.assertEqual(self.runner.install_calls(), [])
        self.assertEqual(self.launched, 0)

    def test_demo_approval_records_recent_and_shows_session_summary(self) -> None:
        confirmation = prepare_demo(self.backend, "abc1def")
        apply_if_approved(self.backend, confirmation, approved=True, launch=True)
        recent = record_demo_if_needed([], confirmation)
        self.assertEqual(len(recent), 1)
        self.assertEqual(recent[0].source_repo, "umyelab/LabGym")
        self.assertEqual(recent[0].commit, DEMO_SHA)
        status = self.backend.status()
        summary = format_session_summary(status)
        self.assertIn("Installed: Selected Commit", summary)
        self.assertIn("umyelab/LabGym @ %s" % DEMO_SHA[:7], summary)
        self.assertIn("Official Release session: not running", summary)
        self.assertIn("Selected Commit session: running", summary)
        self.assertEqual(len(summary.splitlines()), 4)
        self.assertNotIn("demo-branch", summary)
        self.assertNotIn("worktrees", summary)
        self.assertNotIn("Branch:", summary)
        self.assertNotIn("Message:", summary)
        self.assertNotIn(DEMO_SHA, summary)
        from labgym_launcher.confirm import format_status

        details = format_status(status)
        self.assertIn("Source repo: umyelab/LabGym", details)
        self.assertIn("Commit: %s" % DEMO_SHA, details)
        self.assertIn("Branch: demo-branch", details)
        self.assertIn("Message: Add selected-commit UI", details)
        self.assertIn(str(self.data_dir / "worktrees" / "demo"), details)
        label = recent[0].label()
        self.assertLessEqual(len(label.splitlines()), 2)
        self.assertIn("umyelab/LabGym @ %s" % DEMO_SHA[:7], label)
        self.assertIn("Add selected-commit UI", label)
        self.assertNotIn("detached commit", label)
        self.assertNotIn("Branch:", label)
        self.assertIn("<br>", recent[0].html_label())
        self.assertEqual(recent[0].html_label().count("<br>"), 1)
        self.assertIsNone(recent[0].alias)

    def test_rerecording_selected_commit_preserves_alias(self) -> None:
        confirmation = prepare_demo(self.backend, "abc1def")
        apply_if_approved(self.backend, confirmation, approved=True, launch=True)
        recent = record_demo_if_needed([], confirmation)
        recent = set_recent_alias(recent, 0, "Courtship demo")
        confirmation_again = prepare_demo(self.backend, "abc1def")
        recent = record_demo_if_needed(recent, confirmation_again)
        self.assertEqual(len(recent), 1)
        self.assertEqual(recent[0].alias, "Courtship demo")
        self.assertEqual(recent[0].commit, DEMO_SHA)
        self.assertEqual(recent[0].source_repo, "umyelab/LabGym")

    def test_repeated_official_release_skips_transition(self) -> None:
        confirmation = prepare_home(self.backend)
        apply_if_approved(self.backend, confirmation, approved=True, launch=True)
        self.runner.calls.clear()
        selection = select_official_release(self.backend)
        self.assertEqual(selection.outcome, ALREADY_ACTIVE)
        self.assertIsNone(selection.confirmation)
        self.assertIn("Official Release", selection.message)
        self.assertEqual(_transition_ops(self.runner), [])
        self.assertFalse(_metadata_ops(self.runner))
        copy = already_active_success_message(HOME, True)
        self.assertTrue(copy.startswith("Official Release started."))
        self.assertIn("already active", copy)
        self.assertIn("no installation was necessary", copy)
        self.assertIn("LabGym started successfully", copy)
        self.assertNotIn("still usable", copy)
        self.backend.launch(wait=False)
        self.assertEqual(self.launched, 1)
        blocked = self.backend.launch(wait=False)
        self.assertTrue(blocked.blocked)
        self.assertEqual(self.launched, 1)

    def test_repeated_same_commit_skips_transition(self) -> None:
        confirmation = prepare_demo(self.backend, "abc1def")
        apply_if_approved(self.backend, confirmation, approved=True, launch=True)
        self.runner.calls.clear()
        selection = select_selected_commit(self.backend, "abc1def")
        self.assertEqual(selection.outcome, ALREADY_ACTIVE)
        self.assertIsNone(selection.confirmation)
        self.assertIn("selected commit", selection.message)
        self.assertEqual(_transition_ops(self.runner), [])
        self.assertFalse(_metadata_ops(self.runner))
        self.backend.launch(wait=False)
        self.assertEqual(self.launched, 1)
        blocked = self.backend.launch(wait=False)
        self.assertTrue(blocked.blocked)
        self.assertEqual(self.launched, 1)

    def test_real_target_change_still_confirms(self) -> None:
        confirmation = prepare_home(self.backend)
        apply_if_approved(self.backend, confirmation, approved=True, launch=True)
        self.runner.calls.clear()
        selection = select_selected_commit(self.backend, "abc1def")
        self.assertEqual(selection.outcome, NEEDS_CONFIRM)
        self.assertIsNotNone(selection.confirmation)
        self.assertEqual(selection.confirmation.action, "demo")
        self.assertTrue(selection.confirmation.needs_install)
        self.assertTrue(_transition_ops(self.runner))
        self.assertEqual(self.launched, 1)

    def test_stale_official_release_still_confirms(self) -> None:
        confirmation = prepare_home(self.backend)
        apply_if_approved(self.backend, confirmation, approved=True, launch=False)
        self.runner.heads[str(self.data_dir / "worktrees" / "home")] = (
            "cccccccccccccccccccccccccccccccccccccccc"
        )
        selection = select_official_release(self.backend)
        self.assertEqual(selection.outcome, NEEDS_CONFIRM)
        self.assertIsNotNone(selection.confirmation)


def _transition_ops(runner: FakeRunner):
    ops = []
    for call in runner.calls:
        if call and call[0] == "git" and (
            "clone" in call or "fetch" in call or "checkout" in call
        ):
            ops.append(call)
        elif len(call) >= 4 and call[2] == "pip" and "--dry-run" in call:
            ops.append(call)
    return ops


def _metadata_ops(runner: FakeRunner):
    ops = []
    for call in runner.calls:
        if call and call[0] == "git" and (
            (len(call) > 1 and call[1] == "log") or "for-each-ref" in call
        ):
            ops.append(call)
    return ops


class GuiSummaryAndErrorTests(unittest.TestCase):
    def test_compact_summary_includes_both_running_flags(self) -> None:
        from labgym_launcher.models import LauncherStatus

        status = LauncherStatus(
            mode="demo",
            requested="abc1",
            resolved="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            pip_spec="/tmp/demo",
            source_repo="alice/LabGym",
            commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            pypi_version=None,
            installed_labgym="3.0.1",
            installed_source="file:///tmp/demo",
            checkout_path="/tmp/demo",
            branch_name="demo-branch",
            commit_subject="Add selected-commit UI",
            home_checkout="/tmp/home",
            demo_checkout="/tmp/demo",
            data_dir="/tmp/data",
            rollback_available=True,
            official_session_active=True,
            selected_commit_session_active=True,
        )
        summary = format_session_summary(status)
        self.assertEqual(len(summary.splitlines()), 4)
        self.assertIn("Installed: Selected Commit", summary)
        self.assertIn("alice/LabGym @ aaaaaaa", summary)
        self.assertIn("Official Release session: running", summary)
        self.assertIn("Selected Commit session: running", summary)
        self.assertNotIn("Active checkout:", summary)
        self.assertNotIn("Data dir:", summary)

    def test_gui_error_rewrites_cli_demo_usage(self) -> None:
        from labgym_launcher.errors import InvalidHashError
        from labgym_launcher.gui_flow import (
            CLI_DEMO_USAGE,
            GUI_EMPTY_COMMIT_ERROR,
            gui_error_text,
            selected_commit_action_enabled,
            remembered_actions_enabled,
            remove_remembered_confirm_text,
        )

        usage_error = InvalidHashError(
            "Received source repo 'umyelab/LabGym' without a commit hash. "
            "%s Current environment was not changed." % CLI_DEMO_USAGE
        )
        self.assertEqual(gui_error_text(usage_error), GUI_EMPTY_COMMIT_ERROR)
        self.assertNotIn("Usage: demo", gui_error_text(usage_error))
        required = InvalidHashError(
            "A selected commit hash is required. %s Current environment was not changed."
            % CLI_DEMO_USAGE
        )
        self.assertEqual(gui_error_text(required), GUI_EMPTY_COMMIT_ERROR)
        other = InvalidHashError(
            "Selected commit 'master' is not a git commit hash. "
            "Current environment was not changed."
        )
        self.assertIn("not a git commit hash", gui_error_text(other))
        self.assertNotIn("Usage: demo", gui_error_text(other))

        self.assertFalse(selected_commit_action_enabled(""))
        self.assertFalse(selected_commit_action_enabled("   "))
        self.assertTrue(selected_commit_action_enabled("abc1"))
        self.assertFalse(selected_commit_action_enabled("abc1", working=True))
        self.assertFalse(remembered_actions_enabled(-1, 0))
        self.assertFalse(remembered_actions_enabled(None, 2))
        self.assertTrue(remembered_actions_enabled(0, 2))
        self.assertFalse(remembered_actions_enabled(0, 2, working=True))

        aliased = remove_remembered_confirm_text(
            "alice/LabGym",
            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            "Courtship demo",
        )
        self.assertIn("Remove this remembered commit from the list?", aliased)
        self.assertIn('Remembered entry: "Courtship demo"', aliased)
        self.assertNotIn("alice/LabGym @", aliased)
        plain = remove_remembered_confirm_text(
            "alice/LabGym",
            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            "",
        )
        self.assertIn('Remembered entry: "alice/LabGym @ aaaaaaa"', plain)
        self.assertIn(
            "This does not uninstall LabGym or change the current environment.",
            plain,
        )

    def test_restore_success_message_avoids_rollback_word(self) -> None:
        from labgym_launcher.gui_flow import applied_success_message

        text = applied_success_message("rollback", False)
        self.assertIn("Restore Official Release complete", text)
        self.assertNotIn("Rollback complete", text)


if __name__ == "__main__":
    unittest.main()
