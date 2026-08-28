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
    home_checkout: str
    demo_checkout: str
    data_dir: str
    rollback_available: bool
