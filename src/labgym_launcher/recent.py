import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence

from labgym_launcher.confirm import format_selected_commit_html, format_selected_commit_label

LOGGER = logging.getLogger("labgym_launcher")
RECENT_FILENAME = "recent_demos.json"


@dataclass(frozen=True)
class RecentDemo:
    source_repo: str
    commit: str
    branch_name: Optional[str] = None
    subject: Optional[str] = None

    def label(self) -> str:
        return format_selected_commit_label(
            self.source_repo,
            self.commit,
            self.branch_name,
            self.subject,
        )

    def html_label(self) -> str:
        return format_selected_commit_html(
            self.source_repo,
            self.commit,
            self.branch_name,
            self.subject,
        )


def recent_path(data_dir: Path) -> Path:
    return data_dir / RECENT_FILENAME


def load_recent(data_dir: Path) -> List[RecentDemo]:
    path = recent_path(data_dir)
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        LOGGER.info("could not read recent selected-commit list: %s", exc)
        return []
    if not isinstance(payload, list):
        return []
    recent: List[RecentDemo] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        source = str(item.get("source_repo", "")).strip()
        commit = str(item.get("commit", "")).strip()
        branch_name = str(item.get("branch") or item.get("branch_name") or "").strip() or None
        subject = str(item.get("subject") or "").strip() or None
        if source and commit:
            recent.append(
                RecentDemo(
                    source,
                    commit,
                    branch_name=branch_name,
                    subject=subject,
                )
            )
    return dedupe_recent(recent)


def save_recent(data_dir: Path, recent: Sequence[RecentDemo]) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    payload = []
    for item in dedupe_recent(recent):
        entry = {"commit": item.commit, "source_repo": item.source_repo}
        if item.branch_name:
            entry["branch"] = item.branch_name
        if item.subject:
            entry["subject"] = item.subject
        payload.append(entry)
    recent_path(data_dir).write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def dedupe_recent(items: Sequence[RecentDemo]) -> List[RecentDemo]:
    seen = set()
    ordered: List[RecentDemo] = []
    for item in items:
        key = (item.source_repo, item.commit)
        if key in seen:
            continue
        seen.add(key)
        ordered.append(item)
    return ordered


def record_recent(
    recent: Sequence[RecentDemo],
    source_repo: str,
    commit: Optional[str],
    branch_name: Optional[str] = None,
    subject: Optional[str] = None,
) -> List[RecentDemo]:
    if not source_repo or not commit:
        return list(recent)
    item = RecentDemo(
        source_repo=source_repo,
        commit=commit,
        branch_name=branch_name,
        subject=subject,
    )
    updated = [
        entry
        for entry in recent
        if (entry.source_repo, entry.commit) != (item.source_repo, item.commit)
    ]
    updated.insert(0, item)
    return updated


def replace_recent(
    recent: Sequence[RecentDemo],
    index: int,
    source_repo: str,
    commit: str,
) -> List[RecentDemo]:
    updated = list(recent)
    updated[index] = RecentDemo(source_repo, commit)
    return dedupe_recent(updated)


def remove_recent(recent: Sequence[RecentDemo], index: int) -> List[RecentDemo]:
    updated = list(recent)
    del updated[index]
    return updated
