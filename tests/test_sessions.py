import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from labgym_launcher.backend import LauncherBackend
from labgym_launcher.gui_flow import (
    ALREADY_ACTIVE,
    SESSION_BLOCKED,
    apply_if_approved,
    select_official_release,
    select_selected_commit,
)
from labgym_launcher.sessions import (
    OFFICIAL_RELEASE_SESSION,
    OFFICIAL_RELEASE_SESSION_RUNNING,
    SELECTED_COMMIT_SESSION,
    SELECTED_COMMIT_SESSION_RUNNING,
    SessionRegistry,
    duplicate_session_message,
    session_class_for_action,
)
from labgym_launcher.constants import DEMO, HOME
from fakes import FakeRunner


class SessionRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = TemporaryDirectory()
        self.alive = set()
        self.registry = SessionRegistry(
            Path(self.temp.name),
            is_alive=lambda pid: pid in self.alive,
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_duplicate_official_release_is_blocked_until_exit(self) -> None:
        self.alive.add(11)
        self.registry.register(OFFICIAL_RELEASE_SESSION, 11)
        self.assertTrue(self.registry.has_active(OFFICIAL_RELEASE_SESSION))
        self.assertEqual(
            self.registry.block_reason(OFFICIAL_RELEASE_SESSION),
            OFFICIAL_RELEASE_SESSION_RUNNING,
        )
        self.assertFalse(self.registry.has_active(SELECTED_COMMIT_SESSION))
        self.alive.remove(11)
        self.assertFalse(self.registry.has_active(OFFICIAL_RELEASE_SESSION))

    def test_official_and_selected_commit_can_run_together(self) -> None:
        self.alive.update({11, 22})
        self.registry.register(OFFICIAL_RELEASE_SESSION, 11)
        self.registry.register(SELECTED_COMMIT_SESSION, 22)
        self.assertTrue(self.registry.has_active(OFFICIAL_RELEASE_SESSION))
        self.assertTrue(self.registry.has_active(SELECTED_COMMIT_SESSION))
        self.assertIsNone(self.registry.block_reason(None))

    def test_registering_one_class_does_not_clobber_the_other(self) -> None:
        self.alive.update({11, 22})
        self.registry.register(OFFICIAL_RELEASE_SESSION, 11)
        self.registry.register(SELECTED_COMMIT_SESSION, 22)
        self.registry.unregister(OFFICIAL_RELEASE_SESSION)
        self.assertFalse(self.registry.has_active(OFFICIAL_RELEASE_SESSION))
        self.assertTrue(self.registry.has_active(SELECTED_COMMIT_SESSION))


class SessionPolicyTests(unittest.TestCase):
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

    def test_first_official_release_launch_succeeds(self) -> None:
        confirmation = self.backend.prepare_home()
        self.backend.apply(confirmation, approved=True)
        result = self.backend.launch(
            wait=False,
            session_class=session_class_for_action(HOME),
        )
        self.assertTrue(result.started)
        self.assertFalse(result.blocked)
        self.assertEqual(self.launched, 1)
        self.assertTrue(self.backend.sessions.has_active(OFFICIAL_RELEASE_SESSION))

    def test_second_official_release_launch_is_blocked(self) -> None:
        confirmation = self.backend.prepare_home()
        self.backend.apply(confirmation, approved=True)
        first = self.backend.launch(
            wait=False,
            session_class=session_class_for_action(HOME),
        )
        second = self.backend.launch(
            wait=False,
            session_class=session_class_for_action(HOME),
        )
        self.assertTrue(first.started)
        self.assertTrue(second.blocked)
        self.assertFalse(second.started)
        self.assertEqual(second.message, OFFICIAL_RELEASE_SESSION_RUNNING)
        self.assertIn("already running", second.message)
        self.assertIn("did not start another Official Release", second.message)
        self.assertEqual(self.launched, 1)
        selection = select_official_release(self.backend)
        self.assertEqual(selection.outcome, ALREADY_ACTIVE)

    def test_first_selected_commit_launch_succeeds(self) -> None:
        confirmation = self.backend.prepare_demo("abc1def")
        self.backend.apply(confirmation, approved=True)
        result = self.backend.launch(
            wait=False,
            session_class=session_class_for_action(DEMO),
        )
        self.assertTrue(result.started)
        self.assertEqual(self.launched, 1)
        self.assertTrue(self.backend.sessions.has_active(SELECTED_COMMIT_SESSION))

    def test_second_selected_commit_launch_is_blocked(self) -> None:
        confirmation = self.backend.prepare_demo("abc1def")
        self.backend.apply(confirmation, approved=True)
        self.backend.launch(wait=False, session_class=session_class_for_action(DEMO))
        second = self.backend.launch(
            wait=False,
            session_class=session_class_for_action(DEMO),
        )
        self.assertTrue(second.blocked)
        self.assertEqual(second.message, SELECTED_COMMIT_SESSION_RUNNING)
        self.assertIn("already running", second.message)
        self.assertIn("did not start another Selected Commit", second.message)
        self.assertEqual(self.launched, 1)
        selection = select_selected_commit(self.backend, "abc1def")
        self.assertEqual(selection.outcome, ALREADY_ACTIVE)
        other = select_selected_commit(self.backend, "ffffeeee")
        self.assertEqual(other.outcome, SESSION_BLOCKED)
        self.assertEqual(other.message, SELECTED_COMMIT_SESSION_RUNNING)

    def test_official_release_and_selected_commit_can_run_concurrently(self) -> None:
        home = self.backend.prepare_home()
        self.backend.apply(home, approved=True)
        home_launch = self.backend.launch(
            wait=False,
            session_class=session_class_for_action(HOME),
        )
        demo = self.backend.prepare_demo("abc1def")
        self.backend.apply(demo, approved=True)
        demo_launch = self.backend.launch(
            wait=False,
            session_class=session_class_for_action(DEMO),
        )
        self.assertTrue(home_launch.started)
        self.assertTrue(demo_launch.started)
        self.assertFalse(home_launch.blocked)
        self.assertFalse(demo_launch.blocked)
        self.assertEqual(self.launched, 2)
        self.assertTrue(self.backend.sessions.has_active(OFFICIAL_RELEASE_SESSION))
        self.assertTrue(self.backend.sessions.has_active(SELECTED_COMMIT_SESSION))
        status = self.backend.status()
        self.assertTrue(status.official_session_active)
        self.assertTrue(status.selected_commit_session_active)

    def test_apply_if_approved_records_session_and_blocks_duplicate(self) -> None:
        confirmation = self.backend.prepare_home()
        first = apply_if_approved(self.backend, confirmation, True, True)
        second_selection = select_official_release(self.backend)
        self.assertEqual(first, "applied")
        self.assertEqual(second_selection.outcome, ALREADY_ACTIVE)
        blocked = self.backend.launch(
            wait=False,
            session_class=session_class_for_action(HOME),
        )
        self.assertTrue(blocked.blocked)
        self.assertEqual(self.launched, 1)

    def test_session_can_launch_again_after_exit(self) -> None:
        confirmation = self.backend.prepare_home()
        self.backend.apply(confirmation, approved=True)
        self.backend.launch(wait=False, session_class=session_class_for_action(HOME))
        self.backend.end_session(OFFICIAL_RELEASE_SESSION)
        again = self.backend.launch(
            wait=False,
            session_class=session_class_for_action(HOME),
        )
        self.assertTrue(again.started)
        self.assertEqual(self.launched, 2)

    def test_duplicate_messages_are_class_specific(self) -> None:
        self.assertEqual(
            duplicate_session_message(OFFICIAL_RELEASE_SESSION),
            OFFICIAL_RELEASE_SESSION_RUNNING,
        )
        self.assertEqual(
            duplicate_session_message(SELECTED_COMMIT_SESSION),
            SELECTED_COMMIT_SESSION_RUNNING,
        )


if __name__ == "__main__":
    unittest.main()
