import logging
import sys
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

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
    github_url,
    parse_demo_request,
    resolve_commit,
    resolve_release_tag,
    retarget_working_tree,
    validate_source_repo,
)
from labgym_launcher.models import Confirmation, DepChange, LauncherStatus
from labgym_launcher.pipops import PipOps
from labgym_launcher.runner import CommandRunner
from labgym_launcher.state import load_state, save_state, state_value
from labgym_launcher.support import (
    default_data_dir,
    demo_checkout_path,
    fetch_latest_pypi_version,
    home_checkout_path,
)

LOGGER = logging.getLogger("labgym_launcher")

PypiFetcher = Callable[[], str]
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
        launch_impl: Optional[LaunchImpl] = None,
        canonical_source: str = CANONICAL_SOURCE,
    ) -> None:
        self.data_dir = Path(data_dir) if data_dir else default_data_dir()
        self.runner = runner or CommandRunner()
        self.python = python or sys.executable
        self.fetch_pypi_version = fetch_pypi_version or fetch_latest_pypi_version
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
                "Home uses the persistent canonical checkout for official PyPI release %s (tag %s)."
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
        return self._prepare(
            action=DEMO,
            requested=requested,
            resolved=full_hash,
            pip_spec=str(self.demo_path),
            source_repo=source,
            checkout_path=str(self.demo_path),
            commit=full_hash,
            pypi_version=None,
            extra_notes=(
                "Demo retargets the same persistent checkout; a new clone is not created per commit.",
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
                    "Use rollback to restore the latest official LabGym PyPI release.\n"
                    "%s" % restore_error
                )
            raise InstallFailedError(message) from exc
        self._save_success(confirmation)

    def launch(self) -> None:
        state = load_state(self.data_dir)
        checkout = state_value(state, "checkout_path")
        LOGGER.info(
            "launching LabGym from checkout %s",
            checkout or "current environment",
        )
        if self.launch_impl is not None:
            code = self.launch_impl()
        else:
            result = self.runner.run(
                [self.python, "-m", LABGYM_MODULE],
                cwd=checkout,
                capture=False,
            )
            code = result.returncode
        if code != 0:
            raise LaunchRefusedError(
                "LabGym exited with status %s. "
                "Unresolved hashes and dependency failures never reach launch. "
                "If this followed a successful install, the selected revision remains installed "
                "and rollback to home is available." % code
            )

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
            home_checkout=str(self.home_path),
            demo_checkout=str(self.demo_path),
            data_dir=str(self.data_dir),
            rollback_available=True,
        )

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
            "Rollback to the latest official LabGym PyPI release remains available.",
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
            },
        )
