import unittest

from labgym_launcher.confirm import (
    format_confirmation,
    format_selected_commit_html,
    format_selected_commit_label,
    format_status,
)
from labgym_launcher.constants import OFFICIAL_RELEASE_LABEL
from labgym_launcher.gui_flow import format_session_summary
from labgym_launcher.models import Confirmation, DepChange, LauncherStatus


class ConfirmFormatTests(unittest.TestCase):
    def test_includes_comparison_and_approval_context(self) -> None:
        confirmation = Confirmation(
            action="demo",
            requested="abc1",
            resolved="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            pip_spec="/tmp/demo",
            source_repo="alice/LabGym",
            checkout_path="/tmp/demo",
            commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            pypi_version=None,
            current_labgym="3.0.0",
            current_source="LabGym==3.0.0",
            changes=(
                DepChange(name="labgym", current="3.0.0", planned="3.0.1", action="change"),
            ),
            needs_install=True,
            notes=("Restore Official Release remains available.",),
            branch_name="demo-branch",
            commit_subject="Add selected-commit UI",
        )
        text = format_confirmation(confirmation)
        self.assertTrue(text.startswith("Action: Selected Commit"))
        self.assertLess(text.index("Action: Selected Commit"), text.index("\nDetails\n"))
        self.assertLess(text.index("Target: abc1"), text.index("\nDetails\n"))
        self.assertLess(
            text.index("Dependencies will change: yes"), text.index("\nDetails\n")
        )
        self.assertLess(text.index("LabGym will launch: yes"), text.index("\nDetails\n"))
        self.assertLess(text.index("LabGym will launch:"), text.index("Checkout:"))
        self.assertIn("Source repo: alice/LabGym", text.split("Details")[0])
        self.assertIn("Commit: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", text.split("Details")[0])
        self.assertIn("Requested: abc1", text)
        self.assertIn("Checkout: /tmp/demo", text)
        self.assertIn("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", text)
        self.assertIn("Branch: demo-branch", text)
        self.assertIn("Message: Add selected-commit UI", text)
        self.assertIn("labgym: 3.0.0 -> 3.0.1 (change)", text)
        self.assertIn("Install required: yes", text)
        self.assertIn("Restore Official Release remains available.", text)
        self.assertNotIn("pip-reported", text)
        self.assertNotIn("in this stage", text)
        self.assertNotIn("LabGym Launcher confirmation\n", text)

    def test_official_release_action_is_capitalized(self) -> None:
        confirmation = Confirmation(
            action="home",
            requested="home",
            resolved="3.0.1",
            pip_spec="/tmp/home",
            source_repo="umyelab/LabGym",
            checkout_path="/tmp/home",
            commit="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            pypi_version="3.0.1",
            current_labgym="3.0.0",
            current_source="LabGym==3.0.0",
            changes=(),
            needs_install=True,
            notes=(),
        )
        text = format_confirmation(confirmation)
        self.assertEqual(OFFICIAL_RELEASE_LABEL, "Official Release")
        self.assertTrue(text.startswith("Action: Official Release"))
        self.assertIn("PyPI version: 3.0.1", text.split("Details")[0])
        self.assertIn("LabGym will launch: yes", text.split("Details")[0])
        self.assertIn("none listed", text)
        self.assertNotIn("pip-reported", text)

    def test_restore_confirmation_says_labgym_will_not_launch(self) -> None:
        confirmation = Confirmation(
            action="rollback",
            requested="home",
            resolved="3.0.1",
            pip_spec="/tmp/home",
            source_repo="umyelab/LabGym",
            checkout_path="/tmp/home",
            commit="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            pypi_version="3.0.1",
            current_labgym="3.0.0",
            current_source="LabGym==3.0.0",
            changes=(),
            needs_install=True,
            notes=("Restore Official Release does not launch LabGym.",),
        )
        text = format_confirmation(confirmation)
        self.assertTrue(text.startswith("Action: Restore Official Release"))
        self.assertIn("LabGym will launch: no", text.split("Details")[0])
        self.assertNotIn("LabGym will launch: yes", text)
        self.assertIn("Restore Official Release does not launch LabGym.", text)

    def test_selected_commit_label_is_compact_two_lines(self) -> None:
        label = format_selected_commit_label(
            "alice/LabGym",
            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            "demo-branch",
            "Add selected-commit UI",
        )
        lines = label.splitlines()
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0], "alice/LabGym @ aaaaaaa")
        self.assertEqual(lines[1], "Add selected-commit UI")
        self.assertNotIn("detached commit", label)
        self.assertNotIn("Branch:", label)
        self.assertNotIn("source branch unknown", label)

    def test_selected_commit_label_omits_unknown_branch(self) -> None:
        label = format_selected_commit_label(
            "alice/LabGym",
            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            None,
            None,
        )
        lines = label.splitlines()
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0], "alice/LabGym @ aaaaaaa")
        self.assertNotIn("detached commit", label)
        self.assertNotIn("source branch unknown", label)

    def test_selected_commit_html_uses_at_most_one_break(self) -> None:
        html = format_selected_commit_html(
            "alice/LabGym",
            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            "demo-branch",
            "Add selected-commit UI",
        )
        self.assertEqual(html.count("<br>"), 1)
        self.assertIn("alice/LabGym @ aaaaaaa", html)
        self.assertIn("Add selected-commit UI", html)
        self.assertNotIn("demo-branch", html)

    def test_selected_commit_label_keeps_full_subject(self) -> None:
        subject = "Fix the selected-commit history UI so it is readable again without packing metadata"
        label = format_selected_commit_label("alice/LabGym", "aaaaaaaa", None, subject)
        lines = label.splitlines()
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[1], subject)
        self.assertNotIn("...", label)

    def test_status_keeps_full_selected_commit_provenance(self) -> None:
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
        )
        details = format_status(status)
        self.assertIn("Source repo: alice/LabGym", details)
        self.assertIn("Commit: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", details)
        self.assertIn("Branch: demo-branch", details)
        self.assertIn("Message: Add selected-commit UI", details)
        summary = format_session_summary(status)
        self.assertEqual(len(summary.splitlines()), 4)
        self.assertIn("Installed: Selected Commit", summary)
        self.assertIn("alice/LabGym @ aaaaaaa", summary)
        self.assertIn("Official Release session: not running", summary)
        self.assertIn("Selected Commit session: not running", summary)
        self.assertNotIn("demo-branch", summary)
        self.assertNotIn("Branch:", summary)
        self.assertNotIn("Message:", summary)
        self.assertNotIn("/tmp/demo", summary)
        self.assertNotIn("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", summary)

    def test_status_uses_unknown_branch_fallback_in_details(self) -> None:
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
            branch_name=None,
            commit_subject="Add selected-commit UI",
            home_checkout="/tmp/home",
            demo_checkout="/tmp/demo",
            data_dir="/tmp/data",
            rollback_available=True,
        )
        details = format_status(status)
        self.assertIn("Branch: source branch unknown", details)
        self.assertNotIn("detached commit", details)
        summary = format_session_summary(status)
        self.assertNotIn("source branch unknown", summary)
        self.assertNotIn("detached commit", summary)


if __name__ == "__main__":
    unittest.main()
