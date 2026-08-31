import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from labgym_launcher.gitops import checkout_revision, describe_commit
from fakes import DEMO_SHA, HOME_SHA, FakeRunner


def _checkout_calls(runner: FakeRunner):
    return [
        call
        for call in runner.calls
        if call and call[0] == "git" and "checkout" in call
    ]


class CheckoutRevisionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = TemporaryDirectory()
        self.repo = Path(self.temp.name) / "worktrees" / "home"
        self.repo.mkdir(parents=True)
        self.runner = FakeRunner()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_detached_checkout_argv_does_not_treat_revision_as_pathspec(self) -> None:
        checkout_revision(self.runner, self.repo, HOME_SHA)
        self.assertEqual(
            _checkout_calls(self.runner),
            [("git", "checkout", "--detach", "--force", HOME_SHA)],
        )

    def test_demo_revision_uses_the_same_detached_argv_shape(self) -> None:
        checkout_revision(self.runner, self.repo, DEMO_SHA)
        self.assertEqual(
            _checkout_calls(self.runner),
            [("git", "checkout", "--detach", "--force", DEMO_SHA)],
        )

    def test_describe_commit_reads_branch_and_subject(self) -> None:
        metadata = describe_commit(self.runner, self.repo, DEMO_SHA)
        self.assertEqual(metadata.branch_name, "demo-branch")
        self.assertEqual(metadata.subject, "Add selected-commit UI")
        ref_calls = [call for call in self.runner.calls if "for-each-ref" in call]
        self.assertTrue(ref_calls)
        self.assertTrue(all("refs/remotes" in call for call in ref_calls))
        self.assertFalse(any("refs/heads" in call for call in ref_calls))

    def test_describe_commit_falls_back_when_no_branch(self) -> None:
        self.runner.branches = {}
        self.runner.subjects = {DEMO_SHA: "Detached work"}
        metadata = describe_commit(self.runner, self.repo, DEMO_SHA)
        self.assertIsNone(metadata.branch_name)
        self.assertEqual(metadata.subject, "Detached work")

    def test_source_branch_comes_from_containing_remote_ref(self) -> None:
        self.runner.tip_branches = {}
        self.runner.branches = {DEMO_SHA: "main"}
        metadata = describe_commit(self.runner, self.repo, DEMO_SHA)
        self.assertEqual(metadata.branch_name, "main")
        contains = [call for call in self.runner.calls if "--contains" in call]
        self.assertTrue(contains)


if __name__ == "__main__":
    unittest.main()
