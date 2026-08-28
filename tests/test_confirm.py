import unittest

from labgym_launcher.confirm import format_confirmation
from labgym_launcher.models import Confirmation, DepChange


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
            notes=("Rollback to the latest official LabGym PyPI release remains available.",),
        )
        text = format_confirmation(confirmation)
        self.assertIn("Requested: abc1", text)
        self.assertIn("Source repo: alice/LabGym", text)
        self.assertIn("Checkout: /tmp/demo", text)
        self.assertIn("labgym: 3.0.0 -> 3.0.1 (change)", text)
        self.assertIn("Install required: yes", text)
        self.assertIn("Rollback to the latest official LabGym PyPI release remains available.", text)


if __name__ == "__main__":
    unittest.main()
