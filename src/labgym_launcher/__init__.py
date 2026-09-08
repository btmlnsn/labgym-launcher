"""LabGym Launcher backend, CLI, and wxPython GUI.

Default: ``labgym-launcher`` or ``python -m labgym_launcher`` opens the GUI.
CLI: ``labgym-launcher --cli ...`` or ``labgym-launcher-cli``.
GUI extra: ``pip install 'labgym-launcher[gui]'`` (wxPython).
The GUI stays thin and delegates policy to :class:`LauncherBackend`.
"""

from labgym_launcher.backend import LauncherBackend
from labgym_launcher.confirm import format_confirmation

__version__ = "0.2.0"

__all__ = ["LauncherBackend", "format_confirmation", "__version__"]
