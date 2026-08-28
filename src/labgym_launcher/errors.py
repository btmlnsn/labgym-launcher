class LauncherError(Exception):
    """User-facing error. ``str(exc)`` is the full detail for CLI and GUI."""


class InvalidHashError(LauncherError):
    pass


class InvalidSourceError(LauncherError):
    pass


class AmbiguousHashError(LauncherError):
    pass


class MissingHashError(LauncherError):
    pass


class UnresolvedHashError(LauncherError):
    pass


class ApprovalRequiredError(LauncherError):
    pass


class InstallFailedError(LauncherError):
    pass


class LaunchRefusedError(LauncherError):
    pass


class DependencyPlanError(LauncherError):
    pass


class GitError(LauncherError):
    pass


class PipError(LauncherError):
    pass


class PypiError(LauncherError):
    pass
