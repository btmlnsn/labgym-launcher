from labgym_launcher.models import Confirmation, LauncherStatus


def format_confirmation(confirmation: Confirmation) -> str:
    lines = [
        "LabGym Launcher confirmation",
        "Action: %s" % confirmation.action,
        "Requested: %s" % confirmation.requested,
        "Source repo: %s" % confirmation.source_repo,
        "Resolved: %s" % confirmation.resolved,
        "Commit: %s" % (confirmation.commit or "none"),
        "PyPI version: %s" % (confirmation.pypi_version or "none"),
        "Checkout: %s" % confirmation.checkout_path,
        "Install spec: %s" % confirmation.pip_spec,
        "Current LabGym: %s" % (confirmation.current_labgym or "not installed"),
        "Current source: %s" % (confirmation.current_source or "unknown"),
        "Install required: %s" % ("yes" if confirmation.needs_install else "no"),
        "",
        "Dependency comparison (current environment vs selected version):",
    ]
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
        "Mode: %s" % (status.mode or "unknown"),
        "Requested: %s" % (status.requested or "none"),
        "Source repo: %s" % (status.source_repo or "none"),
        "Resolved: %s" % (status.resolved or "none"),
        "Commit: %s" % (status.commit or "none"),
        "PyPI version: %s" % (status.pypi_version or "none"),
        "Install spec: %s" % (status.pip_spec or "none"),
        "Installed LabGym: %s" % (status.installed_labgym or "not installed"),
        "Installed source: %s" % (status.installed_source or "unknown"),
        "Active checkout: %s" % (status.checkout_path or "none"),
        "Home checkout: %s" % status.home_checkout,
        "Demo checkout: %s" % status.demo_checkout,
        "Data dir: %s" % status.data_dir,
        "Rollback to home: %s"
        % ("available" if status.rollback_available else "unavailable"),
    ]
    return "\n".join(lines)
