"""Launcher-owned window and process icon setup.

Packaged assets live in labgym_launcher/assets/icons/. Windows process
identity is umyelab.LabGymLauncher, not LabGym's umyelab.LabGym.
"""

from __future__ import annotations

import logging
import sys
from functools import lru_cache
from importlib.resources import files
from pathlib import Path
from typing import Dict, Optional

LOGGER = logging.getLogger("labgym_launcher")

APP_NAME = "LabGym Launcher"
WINDOWS_APP_USER_MODEL_ID = "umyelab.LabGymLauncher"
ICON_PNG = "labgym-launcher.png"
ICON_ICO = "labgym-launcher.ico"
ICON_ICNS = "labgym-launcher.icns"


@lru_cache(maxsize=1)
def packaged_icon_paths() -> Dict[str, Path]:
    root = files("labgym_launcher").joinpath("assets", "icons")
    return {
        "png": Path(str(root.joinpath(ICON_PNG))),
        "ico": Path(str(root.joinpath(ICON_ICO))),
        "icns": Path(str(root.joinpath(ICON_ICNS))),
    }


def _existing(path: Path) -> Optional[Path]:
    return path if path.is_file() else None


def get_frame_icon_path() -> str:
    """Return the platform-appropriate packaged icon path for wx frames.

    Windows uses the multi-size .ico. macOS, Linux, and other Unix
    platforms use the square PNG, which wx can apply as a window icon.
    """
    icons = packaged_icon_paths()
    if sys.platform.startswith("win"):
        chosen = _existing(icons["ico"]) or _existing(icons["png"])
    elif sys.platform == "darwin":
        chosen = _existing(icons["png"]) or _existing(icons["icns"])
    else:
        chosen = _existing(icons["png"]) or _existing(icons["ico"])
    return str(chosen) if chosen is not None else ""


def set_frame_icon(frame) -> None:
    """Apply the packaged launcher icon to a wx frame."""
    try:
        import wx
    except ImportError:
        return
    icon_path = get_frame_icon_path()
    if not icon_path:
        LOGGER.info("launcher frame icon asset not found")
        return
    icon = wx.Icon(icon_path, wx.BITMAP_TYPE_ANY)
    if not icon.IsOk() and sys.platform.startswith("win"):
        png = _existing(packaged_icon_paths()["png"])
        if png is not None:
            icon = wx.Icon(str(png), wx.BITMAP_TYPE_ANY)
    if icon.IsOk():
        frame.SetIcon(icon)
    else:
        LOGGER.info("failed to load launcher frame icon from %s", icon_path)


def set_windows_app_user_model_id() -> None:
    """Set a launcher-specific Windows AppUserModelID before the first window."""
    if not sys.platform.startswith("win"):
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            WINDOWS_APP_USER_MODEL_ID
        )
    except Exception:
        LOGGER.info("failed to set launcher Windows AppUserModelID")


def set_macos_dock_icon() -> None:
    """Set the Dock icon for unbundled macOS runs when AppKit is available."""
    if sys.platform != "darwin":
        return
    try:
        from AppKit import NSApplication, NSImage
    except ImportError:
        return
    icons = packaged_icon_paths()
    chosen = _existing(icons["icns"]) or _existing(icons["png"])
    if chosen is None:
        LOGGER.info("launcher macOS Dock icon asset not found")
        return
    image = NSImage.alloc().initWithContentsOfFile_(str(chosen))
    if image:
        NSApplication.sharedApplication().setApplicationIconImage_(image)
    else:
        LOGGER.info("failed to load launcher macOS Dock icon from %s", chosen)


def setup_application_icons() -> None:
    """Establish process/Dock identity. Safe to call more than once.

    Windows gets a launcher-specific AppUserModelID. macOS gets a Dock
    icon when AppKit is present. Linux uses the frame PNG set later on
    the wx window; there is no extra process-identity API here.
    """
    set_windows_app_user_model_id()
    set_macos_dock_icon()
