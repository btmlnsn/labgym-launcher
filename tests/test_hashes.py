import unittest

from labgym_launcher.errors import InvalidHashError, InvalidSourceError
from labgym_launcher.gitops import parse_demo_request, validate_hash_format, validate_source_repo


class HashFormatTests(unittest.TestCase):
    def test_accepts_short_and_full_hex(self) -> None:
        self.assertEqual(validate_hash_format("abc1"), "abc1")
        self.assertEqual(
            validate_hash_format("AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"),
            "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        )

    def test_rejects_branch_names_and_empty(self) -> None:
        for value in ("master", "HEAD", "v3.0.1", "", "  ", "abc", "zzz1"):
            with self.subTest(value=value):
                with self.assertRaises(InvalidHashError) as raised:
                    validate_hash_format(value)
                self.assertIn("not a git commit hash", str(raised.exception))
                self.assertIn("Selected commit", str(raised.exception))
                self.assertIn("Current environment was not changed", str(raised.exception))


class SourceRepoTests(unittest.TestCase):
    def test_accepts_username_repo(self) -> None:
        self.assertEqual(validate_source_repo("alice/LabGym"), "alice/LabGym")
        self.assertEqual(validate_source_repo("umyelab/LabGym"), "umyelab/LabGym")

    def test_rejects_urls_and_extra_path(self) -> None:
        for value in (
            "https://github.com/alice/LabGym",
            "alice/LabGym.git",
            "alice",
            "alice/LabGym/extra",
            "",
        ):
            with self.subTest(value=value):
                with self.assertRaises(InvalidSourceError):
                    validate_source_repo(value)


class DemoRequestTests(unittest.TestCase):
    def test_hash_only_defaults_to_canonical_source(self) -> None:
        source, commit = parse_demo_request(["abc1def"])
        self.assertEqual(source, "umyelab/LabGym")
        self.assertEqual(commit, "abc1def")

    def test_source_and_hash(self) -> None:
        source, commit = parse_demo_request(["alice/LabGym", "abc1def"])
        self.assertEqual(source, "alice/LabGym")
        self.assertEqual(commit, "abc1def")

    def test_source_without_hash_is_rejected(self) -> None:
        with self.assertRaises(InvalidHashError) as raised:
            parse_demo_request(["alice/LabGym"])
        self.assertIn("without a commit hash", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
