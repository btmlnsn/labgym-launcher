from html import escape
from typing import Optional

from labgym_launcher.constants import (
    DEMO,
    HOME,
    OFFICIAL_RELEASE_LABEL,
    RESTORE_OFFICIAL_LABEL,
    ROLLBACK,
    SELECTED_COMMIT_LABEL,
    SOURCE_BRANCH_UNKNOWN_LABEL,
)
from labgym_launcher.models import Confirmation, LauncherStatus


def display_action(action: str) -> str:
    if action == HOME:
        return OFFICIAL_RELEASE_LABEL
    if action == DEMO:
        return SELECTED_COMMIT_LABEL
    if action == ROLLBACK:
        return RESTORE_OFFICIAL_LABEL
    return action


def display_mode(mode: Optional[str]) -> str:
    if mode == HOME:
        return OFFICIAL_RELEASE_LABEL
    if mode == DEMO:
        return SELECTED_COMMIT_LABEL
    return mode or "unknown"


def display_branch(branch_name: Optional[str]) -> str:
    text = (branch_name or "").strip()
    return text or SOURCE_BRANCH_UNKNOWN_LABEL


def shorten_commit(commit: Optional[str], length: int = 12) -> str:
    text = (commit or "").strip()
    if not text:
        return "none"
    if len(text) > length:
        return text[:length]
    return text


def format_selected_commit_label(
    source_repo: str,
    commit: Optional[str],
    branch_name: Optional[str] = None,
    subject: Optional[str] = None,
) -> str:
    """Compact recent-list label: at most two lines. Branch is omitted."""
    line1 = "%s @ %s" % (source_repo, shorten_commit(commit, 7))
    subject_text = " ".join((subject or "").split())
    if not subject_text:
        return line1
    return "%s\n%s" % (line1, subject_text)


def format_selected_commit_html(
    source_repo: str,
    commit: Optional[str],
    branch_name: Optional[str] = None,
    subject: Optional[str] = None,
) -> str:
    lines = format_selected_commit_label(
        source_repo, commit, branch_name, subject
    ).splitlines()
    if not lines:
        return ""
    headed = ["<b>%s</b>" % escape(lines[0])]
    headed.extend(escape(line) for line in lines[1:])
    return "<div>%s</div>" % "<br>".join(headed)


def format_confirmation(confirmation: Confirmation) -> str:
    lines = [
        "LabGym Launcher confirmation",
        "Action: %s" % display_action(confirmation.action),
        "Requested: %s" % confirmation.requested,
        "Source repo: %s" % confirmation.source_repo,
        "Resolved: %s" % confirmation.resolved,
        "Commit: %s" % (confirmation.commit or "none"),
    ]
    if confirmation.action == DEMO:
        lines.append("Branch: %s" % display_branch(confirmation.branch_name))
        lines.append(
            "Message: %s"
            % ((confirmation.commit_subject or "").strip() or "none")
        )
    lines.extend(
        [
            "PyPI version: %s" % (confirmation.pypi_version or "none"),
            "Checkout: %s" % confirmation.checkout_path,
            "Install spec: %s" % confirmation.pip_spec,
            "Current LabGym: %s" % (confirmation.current_labgym or "not installed"),
            "Current source: %s" % (confirmation.current_source or "unknown"),
            "Install required: %s" % ("yes" if confirmation.needs_install else "no"),
            "",
            "Dependency comparison (current environment vs selected version):",
        ]
    )
    if confirmation.changes:
        for change in confirmation.changes:
            current = change.current or "not installed"
            planned = change.planned or "not in plan"
            lines.append(
                "  %s: %s -> %s (%s)" % (change.name, current, planned, change.action)
            )
    else:
        lines.append("  no pip-reported package changes")
    if confirmation.notes:
        lines.append("")
        lines.extend(confirmation.notes)
    return "\n".join(lines)


def format_status(status: LauncherStatus) -> str:
    lines = [
        "LabGym Launcher status",
        "Mode: %s" % display_mode(status.mode),
        "Requested: %s" % (status.requested or "none"),
        "Source repo: %s" % (status.source_repo or "none"),
        "Resolved: %s" % (status.resolved or "none"),
        "Commit: %s" % (status.commit or "none"),
    ]
    if status.mode == DEMO:
        lines.append("Branch: %s" % display_branch(status.branch_name))
        lines.append(
            "Message: %s" % ((status.commit_subject or "").strip() or "none")
        )
    lines.extend(
        [
            "PyPI version: %s" % (status.pypi_version or "none"),
            "Install spec: %s" % (status.pip_spec or "none"),
            "Installed LabGym: %s" % (status.installed_labgym or "not installed"),
            "Installed source: %s" % (status.installed_source or "unknown"),
            "Active checkout: %s" % (status.checkout_path or "none"),
            "Official Release checkout: %s" % status.home_checkout,
            "Selected commit checkout: %s" % status.demo_checkout,
            "Data dir: %s" % status.data_dir,
            "Rollback to Official Release: %s"
            % ("available" if status.rollback_available else "unavailable"),
            "Official Release session: %s"
            % ("running" if status.official_session_active else "not running"),
            "Selected Commit session: %s"
            % (
                "running"
                if status.selected_commit_session_active
                else "not running"
            ),
        ]
    )
    return "\n".join(lines)
