import logging
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from labgym_launcher.constants import (
    CANONICAL_SOURCE,
    DEMO,
    FREEZE_FILENAME,
    HOME,
    LABGYM_MODULE,
    LOG_FILENAME,
    ROLLBACK,
)
from labgym_launcher.errors import (
    ApprovalRequiredError,
    InstallFailedError,
    LaunchRefusedError,
    PipError,
)
from labgym_launcher.gitops import (
    checkout_revision,
    current_head,
    describe_commit,
    github_url,
    origin_matches,
    parse_demo_request,
    resolve_commit,
    resolve_release_tag,
    retarget_working_tree,
    validate_source_repo,
)
from labgym_launcher.models import Confirmation, DepChange, LauncherStatus, PreflightResult
from labgym_launcher.pipops import PipOps
from labgym_launcher.runner import CommandRunner
from labgym_launcher.state import load_state, save_state, state_value
from labgym_launcher.support import (
    default_data_dir,
    demo_checkout_path,
    fetch_github_branches_where_head,
    fetch_latest_pypi_version,
    home_checkout_path,
)

LOGGER = logging.getLogger("labgym_launcher")

PypiFetcher = Callable[[], str]
CommitBranchFetcher = Callable[[str, str], Tuple[str, ...]]
LaunchImpl = Callable[[], int]


def classify_change(current: Optional[str], planned: Optional[str]) -> str:
    if planned is None:
        return "unchanged"
    if current is None:
        return "install"
    if current == planned:
        return "unchanged"
    return "change"


def compare_dependencies(
    current: Dict[str, str],
    planned: Dict[str, str],
) -> Tuple[DepChange, ...]:
    changes: List[DepChange] = []
    for name in sorted(planned):
        old = current.get(name)
        new = planned[name]
        changes.append(
            DepChange(
                name=name,
                current=old,
                planned=new,
                action=classify_change(old, new),
            )
        )
    return tuple(changes)


class LauncherBackend:
    def __init__(
        self,
        data_dir: Optional[Path] = None,
        runner: Optional[CommandRunner] = None,
        python: Optional[str] = None,
        fetch_pypi_version: Optional[PypiFetcher] = None,
        fetch_commit_branches: Optional[CommitBranchFetcher] = None,
        launch_impl: Optional[LaunchImpl] = None,
        canonical_source: str = CANONICAL_SOURCE,
    ) -> None:
        self.data_dir = Path(data_dir) if data_dir else default_data_dir()
        self.runner = runner or CommandRunner()
        self.python = python or sys.executable
        self.fetch_pypi_version = fetch_pypi_version or fetch_latest_pypi_version
        self.fetch_commit_branches = (
            fetch_commit_branches or fetch_github_branches_where_head
        )
        self.launch_impl = launch_impl
        self.canonical_source = validate_source_repo(canonical_source)
        self.pip = PipOps(self.runner, self.python)
        self.home_path = home_checkout_path(self.data_dir)
        self.demo_path = demo_checkout_path(self.data_dir)

    def log_path(self) -> Path:
        return self.data_dir / LOG_FILENAME

    def prepare_home(self) -> Confirmation:
        LOGGER.info("preparing home (latest official LabGym PyPI release)")
        version = self.fetch_pypi_version()
        url = github_url(self.canonical_source)
        retarget_working_tree(self.runner, self.home_path, url, HOME)
        tag, commit = resolve_release_tag(
            self.runner,
            self.home_path,
            version,
            self.canonical_source,
        )
        checkout_revision(self.runner, self.home_path, commit)
        return self._prepare(
            action=HOME,
            requested=HOME,
            resolved=version,
            pip_spec=str(self.home_path),
            source_repo=self.canonical_source,
            checkout_path=str(self.home_path),
            commit=commit,
            pypi_version=version,
            extra_notes=(
                "The Official Release uses the persistent canonical checkout for PyPI release %s (tag %s)."
                % (version, tag),
            ),
        )

    def prepare_demo(
        self,
        commit: str,
        source_repo: Optional[str] = None,
    ) -> Confirmation:
        source, requested = parse_demo_request(
            [source_repo, commit] if source_repo else [commit],
            default_source=self.canonical_source,
        )
        LOGGER.info("preparing demo %s at %s", source, requested)
        url = github_url(source)
        retarget_working_tree(self.runner, self.demo_path, url, DEMO)
        full_hash = resolve_commit(self.runner, self.demo_path, requested, source)
        checkout_revision(self.runner, self.demo_path, full_hash)
        metadata = describe_commit(self.runner, self.demo_path, full_hash)
        branch_name = metadata.branch_name
        if not branch_name:
            github_branches = self.fetch_commit_branches(source, full_hash)
            if github_branches:
                branch_name = github_branches[0]
        return self._prepare(
            action=DEMO,
            requested=requested,
            resolved=full_hash,
            pip_spec=str(self.demo_path),
            source_repo=source,
            checkout_path=str(self.demo_path),
            commit=full_hash,
            pypi_version=None,
            branch_name=branch_name,
            commit_subject=metadata.subject,
            extra_notes=(
                "A selected commit retargets the same persistent checkout; a new clone is not created per commit.",
            ),
        )

    def prepare_rollback(self) -> Confirmation:
        LOGGER.info("preparing rollback to home")
        confirmation = self.prepare_home()
        return Confirmation(
            action=ROLLBACK,
            requested=HOME,
            resolved=confirmation.resolved,
            pip_spec=confirmation.pip_spec,
            source_repo=confirmation.source_repo,
            checkout_path=confirmation.checkout_path,
            commit=confirmation.commit,
            pypi_version=confirmation.pypi_version,
            current_labgym=confirmation.current_labgym,
            current_source=confirmation.current_source,
            changes=confirmation.changes,
            needs_install=confirmation.needs_install,
            notes=confirmation.notes,
            branch_name=confirmation.branch_name,
            commit_subject=confirmation.commit_subject,
        )

    def apply(self, confirmation: Confirmation, approved: bool = False) -> None:
        if not approved:
            raise ApprovalRequiredError(
                "Installation was not approved. Current environment was not changed."
            )
        if not confirmation.needs_install:
            LOGGER.info("no dependency install required for %s", confirmation.resolved)
            self._save_success(confirmation)
            return
        self.data_dir.mkdir(parents=True, exist_ok=True)
        freeze_path = self.data_dir / FREEZE_FILENAME
        freeze_text = self.pip.freeze()
        freeze_path.write_text(freeze_text, encoding="utf-8")
        LOGGER.info("installing approved spec %s", confirmation.pip_spec)
        try:
            self.pip.install(confirmation.pip_spec)
        except PipError as exc:
            restore_error: Optional[Exception] = None
            if freeze_text.strip():
                try:
                    self.pip.restore_freeze(freeze_path)
                except PipError as restore_exc:
                    restore_error = restore_exc
            message = (
                "Dependency installation failed. LabGym was not launched.\n%s" % exc
            )
            if restore_error is None:
                message += "\nPrevious environment snapshot was restored."
            else:
                message += (
                    "\nRestoring the previous snapshot also failed. "
                    "The environment may be mixed. "
                    "Use rollback to restore the latest Official Release.\n"
                    "%s" % restore_error
                )
            raise InstallFailedError(message) from exc
        self._save_success(confirmation)

    def launch(self, wait: bool = True) -> None:
        state = load_state(self.data_dir)
        checkout = state_value(state, "checkout_path")
        LOGGER.info(
            "launching LabGym from checkout %s wait=%s",
            checkout or "current environment",
            wait,
        )
        if self.launch_impl is not None:
            code = self.launch_impl()
            if wait and code != 0:
                raise LaunchRefusedError(
                    "LabGym exited with status %s. "
                    "Unresolved hashes and dependency failures never reach launch. "
                    "If this followed a successful install, the selected revision remains installed "
                    "and rollback to the Official Release is available." % code
                )
            return
        args = [self.python, "-m", LABGYM_MODULE]
        if wait:
            result = self.runner.run(args, cwd=checkout, capture=False)
            if result.returncode != 0:
                raise LaunchRefusedError(
                    "LabGym exited with status %s. "
                    "Unresolved hashes and dependency failures never reach launch. "
                    "If this followed a successful install, the selected revision remains installed "
                    "and rollback to the Official Release is available." % result.returncode
                )
            return
        LOGGER.info("starting LabGym without waiting for the process to exit")
        self.runner.start(args, cwd=checkout)

    def status(self) -> LauncherStatus:
        state = load_state(self.data_dir)
        installed = self.pip.list_installed()
        source = self.pip.labgym_source_line()
        return LauncherStatus(
            mode=state_value(state, "mode"),
            requested=state_value(state, "requested"),
            resolved=state_value(state, "resolved"),
            pip_spec=state_value(state, "pip_spec"),
            source_repo=state_value(state, "source_repo"),
            commit=state_value(state, "commit"),
            pypi_version=state_value(state, "pypi_version"),
            installed_labgym=installed.get("labgym"),
            installed_source=source,
            checkout_path=state_value(state, "checkout_path"),
            branch_name=state_value(state, "branch_name"),
            commit_subject=state_value(state, "commit_subject"),
            home_checkout=str(self.home_path),
            demo_checkout=str(self.demo_path),
            data_dir=str(self.data_dir),
            rollback_available=True,
        )

    def preflight_official_release(self) -> PreflightResult:
        if self._official_release_is_active():
            return PreflightResult(
                skip_transition=True,
                reason="The Official Release was already active.",
            )
        return PreflightResult(
            skip_transition=False,
            reason="A target change is required.",
        )

    def preflight_selected_commit(
        self,
        commit: str,
        source_repo: Optional[str] = None,
    ) -> PreflightResult:
        source, requested = parse_demo_request(
            [source_repo, commit] if source_repo else [commit],
            default_source=self.canonical_source,
        )
        if self._selected_commit_is_active(source, requested):
            return PreflightResult(
                skip_transition=True,
                reason="The selected commit was already active.",
            )
        return PreflightResult(
            skip_transition=False,
            reason="A target change is required.",
        )

    def _official_release_is_active(self) -> bool:
        state = load_state(self.data_dir)
        if state_value(state, "mode") != HOME:
            return False
        if state_value(state, "source_repo") != self.canonical_source:
            return False
        if not self._paths_equal(state_value(state, "checkout_path"), self.home_path):
            return False
        if not self._labgym_is_installed():
            return False
        commit = state_value(state, "commit")
        return self._checkout_matches_target(
            self.home_path,
            commit,
            github_url(self.canonical_source),
        )

    def _selected_commit_is_active(self, source: str, requested: str) -> bool:
        state = load_state(self.data_dir)
        if state_value(state, "mode") != DEMO:
            return False
        if state_value(state, "source_repo") != source:
            return False
        if not self._paths_equal(state_value(state, "checkout_path"), self.demo_path):
            return False
        if not self._commit_request_matches(requested, state):
            return False
        if not self._labgym_is_installed():
            return False
        commit = state_value(state, "commit")
        return self._checkout_matches_target(
            self.demo_path,
            commit,
            github_url(source),
        )

    def _commit_request_matches(self, requested: str, state: Dict[str, Any]) -> bool:
        req = requested.strip().lower()
        stored_requested = (state_value(state, "requested") or "").strip().lower()
        stored_commit = (state_value(state, "commit") or "").strip().lower()
        if req and req == stored_requested:
            return True
        if stored_commit and (
            stored_commit.startswith(req) or req.startswith(stored_commit)
        ):
            return True
        return False

    def _labgym_is_installed(self) -> bool:
        return self.pip.list_installed().get("labgym") is not None

    def _checkout_matches_target(
        self,
        path: Path,
        expected_commit: Optional[str],
        expected_url: str,
    ) -> bool:
        if not expected_commit:
            return False
        if not (path / ".git").exists():
            return False
        if not origin_matches(self.runner, path, expected_url):
            return False
        head = current_head(self.runner, path)
        return head == expected_commit.strip().lower()

    @staticmethod
    def _paths_equal(left: Optional[str], right: Path) -> bool:
        if not left:
            return False
        return Path(left) == Path(right)

    def _prepare(
        self,
        action: str,
        requested: str,
        resolved: str,
        pip_spec: str,
        source_repo: str,
        checkout_path: str,
        commit: Optional[str],
        pypi_version: Optional[str],
        extra_notes: Tuple[str, ...] = (),
        branch_name: Optional[str] = None,
        commit_subject: Optional[str] = None,
    ) -> Confirmation:
        current = self.pip.list_installed()
        installed_source = self.pip.labgym_source_line()
        planned = self.pip.dry_run(pip_spec)
        changes = compare_dependencies(current, planned)
        needs_install = self._needs_install(
            action=action,
            resolved=resolved,
            source_repo=source_repo,
            checkout_path=checkout_path,
            commit=commit,
            current_labgym=current.get("labgym"),
            changes=changes,
            planned=planned,
        )
        notes = list(extra_notes) + [
            "Packages not listed stay as they are in this stage.",
            "LabGym will not be launched if the hash cannot be resolved or install fails.",
            "Rollback to the latest Official Release remains available.",
        ]
        if needs_install and all(change.action == "unchanged" for change in changes):
            notes.insert(0, "Install is still required to switch the LabGym source.")
        confirmation = Confirmation(
            action=action,
            requested=requested,
            resolved=resolved,
            pip_spec=pip_spec,
            source_repo=source_repo,
            checkout_path=checkout_path,
            commit=commit,
            pypi_version=pypi_version,
            current_labgym=current.get("labgym"),
            current_source=installed_source,
            changes=changes,
            needs_install=needs_install,
            notes=tuple(notes),
            branch_name=branch_name,
            commit_subject=commit_subject,
        )
        LOGGER.info(
            "prepared %s source=%s resolved=%s checkout=%s needs_install=%s",
            action,
            source_repo,
            resolved,
            checkout_path,
            needs_install,
        )
        return confirmation

    def _needs_install(
        self,
        action: str,
        resolved: str,
        source_repo: str,
        checkout_path: str,
        commit: Optional[str],
        current_labgym: Optional[str],
        changes: Tuple[DepChange, ...],
        planned: Dict[str, str],
    ) -> bool:
        if current_labgym is None:
            return True
        if any(change.action != "unchanged" for change in changes):
            return True
        if planned:
            return True
        state = load_state(self.data_dir)
        mode = HOME if action in {HOME, ROLLBACK} else DEMO
        return (
            state_value(state, "mode") != mode
            or state_value(state, "resolved") != resolved
            or state_value(state, "source_repo") != source_repo
            or state_value(state, "checkout_path") != checkout_path
            or state_value(state, "commit") != commit
        )

    def _save_success(self, confirmation: Confirmation) -> None:
        mode = HOME if confirmation.action in {HOME, ROLLBACK} else DEMO
        save_state(
            self.data_dir,
            {
                "mode": mode,
                "requested": confirmation.requested,
                "resolved": confirmation.resolved,
                "pip_spec": confirmation.pip_spec,
                "source_repo": confirmation.source_repo,
                "checkout_path": confirmation.checkout_path,
                "commit": confirmation.commit,
                "pypi_version": confirmation.pypi_version,
                "branch_name": confirmation.branch_name,
                "commit_subject": confirmation.commit_subject,
            },
        )
