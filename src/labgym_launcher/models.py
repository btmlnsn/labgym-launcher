from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass(frozen=True)
class DepChange:
    name: str
    current: Optional[str]
    planned: Optional[str]
    action: str


@dataclass(frozen=True)
class Confirmation:
    action: str
    requested: str
    resolved: str
    pip_spec: str
    source_repo: str
    checkout_path: str
    commit: Optional[str]
    pypi_version: Optional[str]
    current_labgym: Optional[str]
    current_source: Optional[str]
    changes: Tuple[DepChange, ...]
    needs_install: bool
    notes: Tuple[str, ...]
    branch_name: Optional[str] = None
    commit_subject: Optional[str] = None


@dataclass(frozen=True)
class LauncherStatus:
    mode: Optional[str]
    requested: Optional[str]
    resolved: Optional[str]
    pip_spec: Optional[str]
    source_repo: Optional[str]
    commit: Optional[str]
    pypi_version: Optional[str]
    installed_labgym: Optional[str]
    installed_source: Optional[str]
    checkout_path: Optional[str]
    branch_name: Optional[str]
    commit_subject: Optional[str]
    home_checkout: str
    demo_checkout: str
    data_dir: str
    rollback_available: bool


@dataclass(frozen=True)
class PreflightResult:
    skip_transition: bool
    reason: str


@dataclass(frozen=True)
class Selection:
    outcome: str
    confirmation: Optional[Confirmation] = None
    message: str = ""
    target: Optional[str] = None


@dataclass(frozen=True)
class CommitMetadata:
    commit: str
    branch_name: Optional[str]
    subject: Optional[str]
