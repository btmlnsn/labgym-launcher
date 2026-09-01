"""Launcher-managed LabGym session registry.

Policy:
- one Official Release session may be active
- one Selected Commit session may be active
- both may run at the same time
- a second session of the same class is blocked
"""

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from labgym_launcher.constants import DEMO, HOME, SESSIONS_FILENAME

LOGGER = logging.getLogger("labgym_launcher")

OFFICIAL_RELEASE_SESSION = "official_release"
SELECTED_COMMIT_SESSION = "selected_commit"

OFFICIAL_RELEASE_SESSION_RUNNING = (
    "An Official Release session is already running. "
    "The launcher did not start another Official Release instance."
)
SELECTED_COMMIT_SESSION_RUNNING = (
    "A Selected Commit session is already running. "
    "The launcher did not start another Selected Commit instance."
)

IsAlive = Callable[[int], bool]


def process_is_alive(pid: int) -> bool:
    if pid is None or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def session_class_for_action(action: Optional[str]) -> Optional[str]:
    if action == HOME:
        return OFFICIAL_RELEASE_SESSION
    if action == DEMO:
        return SELECTED_COMMIT_SESSION
    return None


def duplicate_session_message(session_class: str) -> str:
    if session_class == SELECTED_COMMIT_SESSION:
        return SELECTED_COMMIT_SESSION_RUNNING
    return OFFICIAL_RELEASE_SESSION_RUNNING


def sessions_path(data_dir: Path) -> Path:
    return Path(data_dir) / SESSIONS_FILENAME


@dataclass(frozen=True)
class SessionRecord:
    session_class: str
    pid: int
    source_repo: Optional[str] = None
    commit: Optional[str] = None
    checkout_path: Optional[str] = None


@dataclass(frozen=True)
class LaunchResult:
    started: bool
    blocked: bool
    message: str = ""

    @classmethod
    def launched(cls) -> "LaunchResult":
        return cls(started=True, blocked=False, message="")

    @classmethod
    def blocked_duplicate(cls, session_class: str) -> "LaunchResult":
        return cls(
            started=False,
            blocked=True,
            message=duplicate_session_message(session_class),
        )


class SessionRegistry:
    def __init__(
        self,
        data_dir: Path,
        is_alive: Optional[IsAlive] = None,
    ) -> None:
        self.data_dir = Path(data_dir)
        self.is_alive = is_alive or process_is_alive

    def has_active(self, session_class: str) -> bool:
        return self.active(session_class) is not None

    def active(self, session_class: str) -> Optional[SessionRecord]:
        self.reap()
        payload = self._load()
        raw = payload.get(session_class)
        if not isinstance(raw, dict):
            return None
        return _record_from_payload(session_class, raw)

    def block_reason(self, session_class: Optional[str]) -> Optional[str]:
        if not session_class:
            return None
        if self.has_active(session_class):
            return duplicate_session_message(session_class)
        return None

    def register(
        self,
        session_class: str,
        pid: int,
        source_repo: Optional[str] = None,
        commit: Optional[str] = None,
        checkout_path: Optional[str] = None,
    ) -> None:
        payload = self._load()
        payload[session_class] = {
            "pid": int(pid),
            "source_repo": source_repo,
            "commit": commit,
            "checkout_path": checkout_path,
        }
        self._save(payload)
        LOGGER.info("registered %s session pid=%s", session_class, pid)

    def unregister(self, session_class: str) -> None:
        payload = self._load()
        if session_class in payload:
            payload.pop(session_class, None)
            self._save(payload)
            LOGGER.info("unregistered %s session", session_class)

    def reap(self) -> None:
        payload = self._load()
        changed = False
        for key in (OFFICIAL_RELEASE_SESSION, SELECTED_COMMIT_SESSION):
            raw = payload.get(key)
            if not isinstance(raw, dict):
                continue
            pid = raw.get("pid")
            try:
                pid_n = int(pid)
            except (TypeError, ValueError):
                payload.pop(key, None)
                changed = True
                continue
            if not self.is_alive(pid_n):
                payload.pop(key, None)
                changed = True
                LOGGER.info("reaped stale %s session pid=%s", key, pid_n)
        if changed:
            self._save(payload)

    def snapshot(self) -> Dict[str, bool]:
        return {
            OFFICIAL_RELEASE_SESSION: self.has_active(OFFICIAL_RELEASE_SESSION),
            SELECTED_COMMIT_SESSION: self.has_active(SELECTED_COMMIT_SESSION),
        }

    def _load(self) -> Dict[str, Any]:
        path = sessions_path(self.data_dir)
        if not path.exists():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            LOGGER.info("could not read session registry: %s", exc)
            return {}
        if not isinstance(payload, dict):
            return {}
        return payload

    def _save(self, payload: Dict[str, Any]) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        path = sessions_path(self.data_dir)
        path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def _record_from_payload(session_class: str, raw: Dict[str, Any]) -> Optional[SessionRecord]:
    try:
        pid = int(raw.get("pid"))
    except (TypeError, ValueError):
        return None
    return SessionRecord(
        session_class=session_class,
        pid=pid,
        source_repo=_optional_text(raw.get("source_repo")),
        commit=_optional_text(raw.get("commit")),
        checkout_path=_optional_text(raw.get("checkout_path")),
    )


def _optional_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
