from typing import Optional

from labgym_launcher.backend import LauncherBackend
from labgym_launcher.confirm import (
    display_mode,
    format_confirmation,
    shorten_commit,
)
from labgym_launcher.constants import DEMO, HOME, ROLLBACK
from labgym_launcher.errors import LauncherError
from labgym_launcher.models import Confirmation, Selection
from labgym_launcher.recent import record_recent
from labgym_launcher.sessions import session_class_for_action

ALREADY_ACTIVE = "already_active"
NEEDS_CONFIRM = "needs_confirm"
SESSION_BLOCKED = "session_blocked"

OFFICIAL_RELEASE_ALREADY_ACTIVE_SUCCESS = (
    "Official Release started.\n"
    "The Official Release was already active, so no installation was necessary. "
    "LabGym started successfully."
)
OFFICIAL_RELEASE_INSTALLED_SUCCESS = (
    "Official Release started.\n"
    "Installation complete. LabGym started successfully."
)
SELECTED_COMMIT_ALREADY_ACTIVE_SUCCESS = (
    "The selected commit was already active, so no installation was necessary. "
    "LabGym started successfully."
)
SELECTED_COMMIT_INSTALLED_SUCCESS = (
    "Installation complete. LabGym started successfully."
)
OFFICIAL_RELEASE_ALREADY_ACTIVE_NO_LAUNCH = (
    "The Official Release was already active, so no installation was necessary. "
    "LabGym was not launched."
)
ROLLBACK_COMPLETE = "Rollback complete. LabGym was not launched."


def prepare_home(backend: LauncherBackend) -> Confirmation:
    return backend.prepare_home()


def prepare_demo(
    backend: LauncherBackend,
    commit: str,
    source_repo: Optional[str] = None,
) -> Confirmation:
    return backend.prepare_demo(commit, source_repo=source_repo)


def prepare_rollback(backend: LauncherBackend) -> Confirmation:
    return backend.prepare_rollback()


def select_official_release(backend: LauncherBackend) -> Selection:
    session_class = session_class_for_action(HOME)
    blocked = backend.sessions.block_reason(session_class)
    preflight = backend.preflight_official_release()
    if blocked and not preflight.skip_transition:
        return Selection(
            outcome=SESSION_BLOCKED,
            message=blocked,
            target=HOME,
        )
    if preflight.skip_transition:
        return Selection(
            outcome=ALREADY_ACTIVE,
            message=preflight.reason,
            target=HOME,
        )
    return Selection(
        outcome=NEEDS_CONFIRM,
        confirmation=backend.prepare_home(),
        target=HOME,
    )


def select_selected_commit(
    backend: LauncherBackend,
    commit: str,
    source_repo: Optional[str] = None,
) -> Selection:
    session_class = session_class_for_action(DEMO)
    blocked = backend.sessions.block_reason(session_class)
    preflight = backend.preflight_selected_commit(commit, source_repo=source_repo)
    if blocked and not preflight.skip_transition:
        return Selection(
            outcome=SESSION_BLOCKED,
            message=blocked,
            target=DEMO,
        )
    if preflight.skip_transition:
        return Selection(
            outcome=ALREADY_ACTIVE,
            message=preflight.reason,
            target=DEMO,
        )
    return Selection(
        outcome=NEEDS_CONFIRM,
        confirmation=backend.prepare_demo(commit, source_repo=source_repo),
        target=DEMO,
    )


def select_rollback(backend: LauncherBackend) -> Selection:
    preflight = backend.preflight_official_release()
    if preflight.skip_transition:
        return Selection(
            outcome=ALREADY_ACTIVE,
            message=preflight.reason,
            target=ROLLBACK,
        )
    return Selection(
        outcome=NEEDS_CONFIRM,
        confirmation=backend.prepare_rollback(),
        target=ROLLBACK,
    )


def already_active_success_message(target: Optional[str], launch: bool) -> str:
    if target in {HOME, ROLLBACK} and launch:
        return OFFICIAL_RELEASE_ALREADY_ACTIVE_SUCCESS
    if target in {HOME, ROLLBACK} and not launch:
        return OFFICIAL_RELEASE_ALREADY_ACTIVE_NO_LAUNCH
    if launch:
        return SELECTED_COMMIT_ALREADY_ACTIVE_SUCCESS
    return "The selected commit was already active, so no installation was necessary. LabGym was not launched."


def applied_success_message(action: str, launch: bool) -> str:
    if action == HOME and launch:
        return OFFICIAL_RELEASE_INSTALLED_SUCCESS
    if action == DEMO and launch:
        return SELECTED_COMMIT_INSTALLED_SUCCESS
    if launch:
        return OFFICIAL_RELEASE_INSTALLED_SUCCESS
    return ROLLBACK_COMPLETE


def apply_if_approved(
    backend: LauncherBackend,
    confirmation: Confirmation,
    approved: bool,
    launch: bool,
) -> str:
    """Apply a confirmation only after explicit approval.

    Launch, when requested, starts LabGym without waiting for it to exit.
    """
    if not approved:
        return "cancelled"
    backend.apply(confirmation, approved=True)
    if launch:
        session_class = session_class_for_action(confirmation.action)
        result = backend.launch(wait=False, session_class=session_class)
        if result.blocked:
            return "blocked"
    return "applied"


def record_demo_if_needed(recent, confirmation: Confirmation):
    if confirmation.action != DEMO:
        return list(recent)
    return record_recent(
        recent,
        confirmation.source_repo,
        confirmation.commit or confirmation.resolved,
        branch_name=confirmation.branch_name,
        subject=confirmation.commit_subject,
    )


def format_session_summary(status) -> str:
    """Compact always-visible session text: mode plus a one-line target."""
    mode = display_mode(status.mode)
    source = status.source_repo or "none"
    if status.mode == DEMO:
        return "Session: %s\n%s @ %s" % (
            mode,
            source,
            shorten_commit(status.commit, 7),
        )
    return "Session: %s\n%s" % (mode, source)


def gui_error_text(exc: BaseException) -> str:
    if isinstance(exc, LauncherError):
        return str(exc)
    return "Unexpected launcher error: %s" % exc


def confirmation_display(confirmation: Confirmation) -> str:
    return format_confirmation(confirmation)
