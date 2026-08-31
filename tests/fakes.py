import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from labgym_launcher.constants import FULL_HASH_PATTERN, HASH_PATTERN
from labgym_launcher.runner import CommandResult, CommandRunner

HOME_SHA = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
DEMO_SHA = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"


class FakeRunner(CommandRunner):
    def __init__(self) -> None:
        self.calls: List[tuple] = []
        self.cwds: List[Optional[str]] = []
        self.clone_code = 0
        self.fetch_code = 0
        self.checkout_code = 0
        self.clean_code = 0
        self.remote_code = 0
        self.resolve_code = 0
        self.resolve_stdout = "%s\n" % DEMO_SHA
        self.resolve_stderr = ""
        self.home_sha = HOME_SHA
        self.origins: Dict[str, str] = {}
        self.pip_list = [{"name": "LabGym", "version": "3.0.0"}]
        self.pip_freeze = "LabGym==3.0.0\n"
        self.pip_report: Dict = {
            "install": [{"metadata": {"name": "LabGym", "version": "3.0.1"}}]
        }
        self.dry_run_code = 0
        self.install_code = 0
        self.restore_code = 0
        self.launch_code = 0
        self.started: List[tuple] = []
        self.heads: Dict[str, str] = {}
        self.subjects: Dict[str, str] = {DEMO_SHA: "Add selected-commit UI"}
        self.branches: Dict[str, str] = {DEMO_SHA: "demo-branch"}
        self.tip_branches: Optional[Dict[str, str]] = None

    def run(
        self,
        args: Sequence[str],
        cwd: Optional[str] = None,
        capture: bool = True,
    ) -> CommandResult:
        argv = tuple(str(part) for part in args)
        self.calls.append(argv)
        self.cwds.append(cwd)
        if argv and argv[0] == "git":
            return self._git(argv, cwd)
        if len(argv) >= 3 and argv[1] == "-m" and argv[2] == "pip":
            return self._pip(argv)
        if len(argv) >= 3 and argv[1] == "-m" and argv[2] == "LabGym":
            return CommandResult(argv, self.launch_code, "", "")
        raise AssertionError("unexpected command: %s" % (argv,))

    def start(self, args: Sequence[str], cwd: Optional[str] = None):
        argv = tuple(str(part) for part in args)
        self.started.append(argv)
        self.cwds.append(cwd)
        return argv

    def install_calls(self) -> List[tuple]:
        return [
            call
            for call in self.calls
            if len(call) >= 4
            and call[2] == "pip"
            and "install" in call
            and "--dry-run" not in call
        ]

    def clone_destinations(self) -> List[str]:
        dests = []
        for call in self.calls:
            if call and call[0] == "git" and "clone" in call:
                dests.append(call[-1])
        return dests

    def _git(self, argv: tuple, cwd: Optional[str]) -> CommandResult:
        if "clone" in argv:
            dest = Path(argv[-1])
            url = argv[-2]
            (dest / ".git").mkdir(parents=True, exist_ok=True)
            self.origins[_path_key(dest)] = url
            return CommandResult(argv, self.clone_code, "", "")
        if "remote" in argv and "get-url" in argv:
            url = self.origins.get(_path_key(cwd), "")
            return CommandResult(argv, self.remote_code, url + "\n", "")
        if "remote" in argv and "set-url" in argv:
            self.origins[_path_key(cwd)] = argv[-1]
            return CommandResult(argv, self.remote_code, "", "")
        if "fetch" in argv:
            return CommandResult(argv, self.fetch_code, "", "")
        if "checkout" in argv:
            if self.checkout_code == 0 and cwd:
                self.heads[_path_key(cwd)] = argv[-1].lower()
            return CommandResult(argv, self.checkout_code, "", "")
        if "clean" in argv:
            return CommandResult(argv, self.clean_code, "", "")
        if "rev-parse" in argv:
            return self._rev_parse(argv, cwd)
        if len(argv) > 1 and argv[1] == "log":
            return self._log(argv)
        if "for-each-ref" in argv:
            return self._for_each_ref(argv)
        if "symbolic-ref" in argv:
            return CommandResult(argv, 1, "", "")
        raise AssertionError("unexpected git command: %s" % (argv,))

    def _rev_parse(self, argv: tuple, cwd: Optional[str] = None) -> CommandResult:
        token = argv[-1]
        core = token[:-9] if token.endswith("^{commit}") else token
        if core.upper() == "HEAD":
            sha = self.heads.get(_path_key(cwd))
            if not sha:
                return CommandResult(argv, 1, "", "fatal: Needed a single revision")
            return CommandResult(argv, 0, sha + "\n", "")
        if self.resolve_code != 0:
            return CommandResult(argv, self.resolve_code, "", self.resolve_stderr)
        if HASH_PATTERN.fullmatch(core) and not re.search(r"[.]" , core):
            stdout = (
                self.resolve_stdout
                if not FULL_HASH_PATTERN.fullmatch(core.lower())
                else core.lower() + "\n"
            )
            return CommandResult(argv, 0, stdout, "")
        return CommandResult(argv, 0, self.home_sha + "\n", "")

    def _log(self, argv: tuple) -> CommandResult:
        revision = argv[-1].lower()
        subject = self.subjects.get(revision, "Test commit")
        return CommandResult(argv, 0, subject + "\n", "")

    def _for_each_ref(self, argv: tuple) -> CommandResult:
        if "refs/heads" in argv and "refs/remotes" not in argv:
            return CommandResult(argv, 0, "", "")
        revision = ""
        if "--points-at" in argv:
            revision = argv[argv.index("--points-at") + 1].lower()
            mapping = self.branches if self.tip_branches is None else self.tip_branches
        elif "--contains" in argv:
            revision = argv[argv.index("--contains") + 1].lower()
            mapping = self.branches
        else:
            mapping = {}
        branch = mapping.get(revision, "")
        if not branch:
            return CommandResult(argv, 0, "", "")
        if not branch.startswith("origin/"):
            branch = "origin/%s" % branch
        return CommandResult(argv, 0, branch + "\n", "")

    def _pip(self, argv: tuple) -> CommandResult:
        if "list" in argv:
            return CommandResult(argv, 0, json.dumps(self.pip_list), "")
        if "freeze" in argv:
            return CommandResult(argv, 0, self.pip_freeze, "")
        if "--dry-run" in argv:
            report = _report_path(argv)
            report.write_text(json.dumps(self.pip_report), encoding="utf-8")
            return CommandResult(argv, self.dry_run_code, "", "")
        if "-r" in argv:
            return CommandResult(argv, self.restore_code, "", "")
        return CommandResult(
            argv, self.install_code, "", "install failed" if self.install_code else ""
        )


def _path_key(path) -> str:
    return str(Path(path)) if path is not None else ""


def _report_path(argv: tuple) -> Path:
    index = argv.index("--report")
    return Path(argv[index + 1])
