import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Tuple
from urllib.error import URLError
from urllib.request import Request, urlopen

from labgym_launcher.constants import (
    DATA_DIR_NAME,
    DEMO_WORKTREE,
    ENV_HOME,
    GITHUB_BRANCHES_WHERE_HEAD_URL,
    HOME_WORKTREE,
    PYPI_JSON_URL,
    USER_AGENT,
    WORKTREES_DIRNAME,
)
from labgym_launcher.errors import PypiError
from labgym_launcher.runner import CommandResult

LOGGER = logging.getLogger("labgym_launcher")


def canonicalize_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def default_data_dir() -> Path:
    override = os.environ.get(ENV_HOME)
    if override:
        return Path(override).expanduser()
    return Path.home() / DATA_DIR_NAME


def worktrees_root(data_dir: Path) -> Path:
    return data_dir / WORKTREES_DIRNAME


def home_checkout_path(data_dir: Path) -> Path:
    return worktrees_root(data_dir) / HOME_WORKTREE


def demo_checkout_path(data_dir: Path) -> Path:
    return worktrees_root(data_dir) / DEMO_WORKTREE


def fetch_latest_pypi_version(url: str = PYPI_JSON_URL) -> str:
    LOGGER.info("querying official LabGym PyPI metadata")
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        },
    )
    try:
        with urlopen(request, timeout=30) as response:
            payload: Any = json.load(response)
    except (URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        raise PypiError(
            "Could not read the latest official LabGym release from PyPI. "
            "Current environment was not changed. "
            "Detail: %s" % exc
        ) from exc
    try:
        version = str(payload["info"]["version"]).strip()
    except (KeyError, TypeError) as exc:
        raise PypiError(
            "PyPI metadata for LabGym did not include a release version. "
            "Current environment was not changed."
        ) from exc
    if not version:
        raise PypiError(
            "PyPI metadata for LabGym included an empty release version. "
            "Current environment was not changed."
        )
    LOGGER.info("latest official LabGym PyPI release is %s", version)
    return version


def fetch_github_branches_where_head(source_repo: str, commit: str) -> Tuple[str, ...]:
    """Return GitHub branch names where ``commit`` is the branch head.

    Failures are ignored so missing provenance never blocks prepare or launch.
    """
    url = GITHUB_BRANCHES_WHERE_HEAD_URL % (source_repo, commit)
    LOGGER.info("querying GitHub source-branch provenance for %s at %s", source_repo, commit)
    request = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": USER_AGENT,
        },
    )
    try:
        with urlopen(request, timeout=15) as response:
            payload: Any = json.load(response)
    except (URLError, TimeoutError, json.JSONDecodeError, OSError, ValueError) as exc:
        LOGGER.info("GitHub branch provenance unavailable: %s", exc)
        return ()
    if not isinstance(payload, list):
        return ()
    names = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if name:
            names.append(name)
    return tuple(names)


def require_ok(result: CommandResult, error_cls, context: str) -> CommandResult:
    if result.returncode == 0:
        return result
    detail = (result.stderr or result.stdout).strip() or "exit %s" % result.returncode
    raise error_cls("%s\nCommand: %s\n%s" % (context, " ".join(result.args), detail))
