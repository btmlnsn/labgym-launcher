import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from labgym_launcher.recent import (
    RecentDemo,
    dedupe_recent,
    load_recent,
    record_recent,
    remove_recent,
    replace_recent,
    save_recent,
)


class RecentDemoTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = TemporaryDirectory()
        self.data_dir = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_dedupe_keeps_first_occurrence(self) -> None:
        items = [
            RecentDemo("alice/LabGym", "abc1"),
            RecentDemo("alice/LabGym", "abc1"),
            RecentDemo("umyelab/LabGym", "def2"),
        ]
        self.assertEqual(
            dedupe_recent(items),
            [
                RecentDemo("alice/LabGym", "abc1"),
                RecentDemo("umyelab/LabGym", "def2"),
            ],
        )

    def test_record_moves_duplicate_to_front(self) -> None:
        recent = [
            RecentDemo("umyelab/LabGym", "1111"),
            RecentDemo("alice/LabGym", "abc1"),
        ]
        updated = record_recent(recent, "alice/LabGym", "abc1")
        self.assertEqual(
            updated,
            [
                RecentDemo("alice/LabGym", "abc1"),
                RecentDemo("umyelab/LabGym", "1111"),
            ],
        )

    def test_load_and_save_round_trip(self) -> None:
        recent = [
            RecentDemo("alice/LabGym", "abc1"),
            RecentDemo("umyelab/LabGym", "def2"),
            RecentDemo("alice/LabGym", "abc1"),
        ]
        save_recent(self.data_dir, recent)
        loaded = load_recent(self.data_dir)
        self.assertEqual(
            loaded,
            [
                RecentDemo("alice/LabGym", "abc1"),
                RecentDemo("umyelab/LabGym", "def2"),
            ],
        )
        payload = json.loads((self.data_dir / "recent_demos.json").read_text(encoding="utf-8"))
        self.assertEqual(len(payload), 2)

    def test_load_missing_file_is_empty(self) -> None:
        self.assertEqual(load_recent(self.data_dir), [])

    def test_replace_and_remove(self) -> None:
        recent = [
            RecentDemo("alice/LabGym", "abc1"),
            RecentDemo("umyelab/LabGym", "def2"),
        ]
        recent = replace_recent(recent, 1, "bob/LabGym", "3333")
        self.assertEqual(recent[1], RecentDemo("bob/LabGym", "3333"))
        recent = remove_recent(recent, 0)
        self.assertEqual(recent, [RecentDemo("bob/LabGym", "3333")])

    def test_label_is_compact_two_lines(self) -> None:
        item = RecentDemo(
            "alice/LabGym",
            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            branch_name="demo-branch",
            subject="Add selected-commit UI",
        )
        label = item.label()
        lines = label.splitlines()
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0], "alice/LabGym @ aaaaaaa")
        self.assertEqual(lines[1], "Add selected-commit UI")
        self.assertNotIn("detached commit", label)
        self.assertNotIn("Branch:", label)
        html = item.html_label()
        self.assertEqual(html.count("<br>"), 1)
        self.assertIn("Add selected-commit UI", html)
        self.assertNotIn("demo-branch", html)

    def test_label_keeps_full_subject_without_ellipsis(self) -> None:
        subject = "Fix the selected-commit history UI so it is readable again without packing metadata"
        item = RecentDemo(
            "alice/LabGym",
            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            subject=subject,
        )
        label = item.label()
        self.assertEqual(label.splitlines()[1], subject)
        self.assertNotIn("...", label)
        self.assertNotIn("...", item.html_label())


if __name__ == "__main__":
    unittest.main()
