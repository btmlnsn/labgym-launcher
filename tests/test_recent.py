import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from labgym_launcher.recent import (
    DISPLAY_ALIAS_MAX,
    DISPLAY_REPO_MAX,
    DISPLAY_SUBJECT_MAX,
    RecentDemo,
    dedupe_recent,
    display_html_label,
    ellipsize_end,
    ellipsize_middle,
    load_recent,
    normalize_alias,
    record_recent,
    remove_recent,
    replace_recent,
    save_recent,
    set_recent_alias,
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

    def test_blank_alias_is_treated_as_absent(self) -> None:
        self.assertIsNone(normalize_alias(None))
        self.assertIsNone(normalize_alias(""))
        self.assertIsNone(normalize_alias("   "))
        self.assertEqual(normalize_alias("  Courtship  demo  "), "Courtship demo")

    def test_alias_create_edit_and_clear(self) -> None:
        recent = [
            RecentDemo("alice/LabGym", "abc1", subject="Add selected-commit UI"),
            RecentDemo("umyelab/LabGym", "def2"),
        ]
        recent = set_recent_alias(recent, 0, "  Courtship demo  ")
        self.assertEqual(recent[0].alias, "Courtship demo")
        self.assertEqual(recent[0].source_repo, "alice/LabGym")
        self.assertEqual(recent[0].commit, "abc1")
        self.assertEqual(recent[0].subject, "Add selected-commit UI")
        recent = set_recent_alias(recent, 0, "Courtship v2")
        self.assertEqual(recent[0].alias, "Courtship v2")
        recent = set_recent_alias(recent, 0, "   ")
        self.assertIsNone(recent[0].alias)
        self.assertEqual(recent[1].alias, None)

    def test_aliases_need_not_be_unique(self) -> None:
        items = [
            RecentDemo("alice/LabGym", "abc1", alias="same label"),
            RecentDemo("bob/LabGym", "def2", alias="same label"),
        ]
        self.assertEqual(dedupe_recent(items), items)

    def test_alias_does_not_change_duplicate_identity(self) -> None:
        items = [
            RecentDemo("alice/LabGym", "abc1", alias="first"),
            RecentDemo("alice/LabGym", "abc1", alias="second"),
        ]
        self.assertEqual(
            dedupe_recent(items),
            [RecentDemo("alice/LabGym", "abc1", alias="first")],
        )

    def test_record_recent_preserves_alias_for_same_entry(self) -> None:
        recent = [
            RecentDemo(
                "alice/LabGym",
                "abc1",
                subject="old subject",
                alias="Courtship demo",
            )
        ]
        updated = record_recent(
            recent,
            "alice/LabGym",
            "abc1",
            subject="Add selected-commit UI",
        )
        self.assertEqual(updated[0].alias, "Courtship demo")
        self.assertEqual(updated[0].subject, "Add selected-commit UI")
        self.assertEqual(updated[0].source_repo, "alice/LabGym")
        self.assertEqual(updated[0].commit, "abc1")

    def test_alias_persists_across_save_and_load(self) -> None:
        recent = [
            RecentDemo("alice/LabGym", "abc1", alias="Courtship demo"),
            RecentDemo("umyelab/LabGym", "def2"),
        ]
        save_recent(self.data_dir, recent)
        loaded = load_recent(self.data_dir)
        self.assertEqual(loaded[0].alias, "Courtship demo")
        self.assertIsNone(loaded[1].alias)
        payload = json.loads((self.data_dir / "recent_demos.json").read_text(encoding="utf-8"))
        self.assertEqual(payload[0]["alias"], "Courtship demo")
        self.assertNotIn("alias", payload[1])

    def test_load_legacy_payload_without_alias_is_empty_alias(self) -> None:
        path = self.data_dir / "recent_demos.json"
        path.write_text(
            json.dumps(
                [{"commit": "abc1", "source_repo": "alice/LabGym", "subject": "Hello"}],
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        loaded = load_recent(self.data_dir)
        self.assertEqual(len(loaded), 1)
        self.assertIsNone(loaded[0].alias)
        self.assertEqual(loaded[0].subject, "Hello")

    def test_label_shows_alias_before_provenance(self) -> None:
        item = RecentDemo(
            "alice/LabGym",
            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            branch_name="demo-branch",
            subject="Add selected-commit UI",
            alias="Courtship demo",
        )
        lines = item.label().splitlines()
        self.assertEqual(lines[0], "Courtship demo")
        self.assertEqual(lines[1], "alice/LabGym @ aaaaaaa")
        self.assertEqual(lines[2], "Add selected-commit UI")
        html = item.html_label()
        self.assertIn("<b>Courtship demo</b>", html)
        self.assertIn("alice/LabGym @ aaaaaaa", html)
        self.assertIn("Add selected-commit UI", html)
        self.assertEqual(html.count("<br>"), 2)
        self.assertNotIn("demo-branch", html)

    def test_label_without_alias_keeps_current_display(self) -> None:
        item = RecentDemo(
            "alice/LabGym",
            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            subject="Add selected-commit UI",
        )
        self.assertEqual(
            item.label().splitlines(),
            ["alice/LabGym @ aaaaaaa", "Add selected-commit UI"],
        )

    def test_html_label_escapes_alias_text(self) -> None:
        item = RecentDemo("alice/LabGym", "abc1", alias="<b>unsafe</b>")
        html = item.html_label()
        self.assertIn("&lt;b&gt;unsafe&lt;/b&gt;", html)
        self.assertNotIn("<b>unsafe</b>", html)

    def test_display_html_truncates_long_alias_only(self) -> None:
        alias = "A" * (DISPLAY_ALIAS_MAX + 12)
        item = RecentDemo(
            "alice/LabGym",
            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            subject="Add selected-commit UI",
            alias=alias,
        )
        display = display_html_label(item)
        self.assertIn("...", display)
        self.assertNotIn(alias, display)
        self.assertEqual(item.alias, alias)
        self.assertIn(alias, item.label())
        self.assertIn(alias, item.html_label())
        self.assertNotIn("...", item.html_label())
        self.assertIn("alice/LabGym @ aaaaaaa", display)

    def test_display_html_truncates_long_repo_and_keeps_hash(self) -> None:
        repo = "verylongorganizationname/extremely-long-repository-name-for-labgym"
        self.assertGreater(len(repo), DISPLAY_REPO_MAX)
        item = RecentDemo(repo, "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", subject="Short")
        display = display_html_label(item)
        self.assertIn("...", display)
        self.assertIn(" @ aaaaaaa", display)
        self.assertNotIn(repo, display)
        self.assertEqual(item.source_repo, repo)
        self.assertEqual(item.commit, "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
        self.assertIn(repo, item.label())
        self.assertIn(repo, item.html_label())
        self.assertNotIn("...", item.html_label())
        displayed_repo = ellipsize_middle(repo, DISPLAY_REPO_MAX)
        self.assertEqual(len(displayed_repo), DISPLAY_REPO_MAX)
        self.assertIn(displayed_repo, display)

    def test_display_html_truncates_long_subject_only(self) -> None:
        subject = "S" * (DISPLAY_SUBJECT_MAX + 20)
        item = RecentDemo("alice/LabGym", "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", subject=subject)
        display = display_html_label(item)
        self.assertIn("...", display)
        self.assertNotIn(subject, display)
        self.assertEqual(item.subject, subject)
        self.assertIn(subject, item.label())
        self.assertIn(subject, item.html_label())
        self.assertNotIn("...", item.html_label())
        self.assertIn("alice/LabGym @ aaaaaaa", display)

    def test_display_html_leaves_short_strings_unchanged(self) -> None:
        item = RecentDemo(
            "alice/LabGym",
            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            subject="Add selected-commit UI",
            alias="Courtship demo",
        )
        display = display_html_label(item)
        self.assertNotIn("...", display)
        self.assertEqual(display, item.html_label())

    def test_display_html_escapes_truncated_alias(self) -> None:
        alias = "<b>" + ("x" * DISPLAY_ALIAS_MAX)
        item = RecentDemo("alice/LabGym", "abc1", alias=alias)
        display = display_html_label(item)
        self.assertIn("&lt;b&gt;", display)
        self.assertNotIn("<b>xxx", display)
        self.assertIn("...", display)

    def test_ellipsize_helpers_keep_short_text(self) -> None:
        self.assertEqual(ellipsize_end("short", 48), "short")
        self.assertEqual(ellipsize_middle("alice/LabGym", 40), "alice/LabGym")
        self.assertTrue(ellipsize_end("n" * 60, DISPLAY_SUBJECT_MAX).endswith("..."))
        self.assertEqual(len(ellipsize_end("n" * 60, DISPLAY_SUBJECT_MAX)), DISPLAY_SUBJECT_MAX)
        self.assertEqual(len(ellipsize_middle("r" * 80, DISPLAY_REPO_MAX)), DISPLAY_REPO_MAX)


if __name__ == "__main__":
    unittest.main()
