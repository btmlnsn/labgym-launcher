import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from labgym_launcher.gitops import checkout_revision
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


if __name__ == "__main__":
    unittest.main()
