import json
import logging
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import List, Optional, Sequence

from labgym_launcher.confirm import format_selected_commit_label

LOGGER = logging.getLogger("labgym_launcher")
RECENT_FILENAME = "recent_demos.json"


def normalize_alias(alias: Optional[str]) -> Optional[str]:
    text = " ".join((alias or "").split())
    return text or None


def _html_from_label(text: str) -> str:
    lines = text.splitlines()
    if not lines:
        return ""
    headed = ["<b>%s</b>" % escape(lines[0])]
    headed.extend(escape(line) for line in lines[1:])
    return "<div>%s</div>" % "<br>".join(headed)


@dataclass(frozen=True)
class RecentDemo:
    source_repo: str
    commit: str
    branch_name: Optional[str] = None
    subject: Optional[str] = None
    alias: Optional[str] = None

    def label(self) -> str:
        provenance = format_selected_commit_label(
            self.source_repo,
            self.commit,
            self.branch_name,
            self.subject,
        )
        alias_text = normalize_alias(self.alias)
        if not alias_text:
            return provenance
        return "\n".join([alias_text] + provenance.splitlines())

    def html_label(self) -> str:
        return _html_from_label(self.label())


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
        alias = normalize_alias(str(item.get("alias") or ""))
        if source and commit:
            recent.append(
                RecentDemo(
                    source,
                    commit,
                    branch_name=branch_name,
                    subject=subject,
                    alias=alias,
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
        if item.alias:
            entry["alias"] = item.alias
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
    alias: Optional[str] = None,
) -> List[RecentDemo]:
    if not source_repo or not commit:
        return list(recent)
    preserved_alias = normalize_alias(alias)
    if preserved_alias is None:
        for entry in recent:
            if (entry.source_repo, entry.commit) == (source_repo, commit):
                preserved_alias = entry.alias
                break
    item = RecentDemo(
        source_repo=source_repo,
        commit=commit,
        branch_name=branch_name,
        subject=subject,
        alias=preserved_alias,
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
    old = updated[index]
    updated[index] = RecentDemo(source_repo, commit, alias=old.alias)
    return dedupe_recent(updated)


def set_recent_alias(
    recent: Sequence[RecentDemo],
    index: int,
    alias: Optional[str],
) -> List[RecentDemo]:
    updated = list(recent)
    item = updated[index]
    updated[index] = RecentDemo(
        source_repo=item.source_repo,
        commit=item.commit,
        branch_name=item.branch_name,
        subject=item.subject,
        alias=normalize_alias(alias),
    )
    return updated


def remove_recent(recent: Sequence[RecentDemo], index: int) -> List[RecentDemo]:
    updated = list(recent)
    del updated[index]
    return updated
