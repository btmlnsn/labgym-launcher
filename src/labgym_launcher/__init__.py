"""LabGym Launcher backend and CLI.

The wxPython GUI is not built in this stage. GUI work should stay thin and
call :class:`LauncherBackend` plus :func:`format_confirmation`.
"""

from labgym_launcher.backend import LauncherBackend
from labgym_launcher.confirm import format_confirmation

__version__ = "0.1.0"

__all__ = ["LauncherBackend", "format_confirmation", "__version__"]
