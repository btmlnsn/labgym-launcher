import json
import logging
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

from labgym_launcher.errors import DependencyPlanError, PipError
from labgym_launcher.runner import CommandRunner
from labgym_launcher.support import canonicalize_name, require_ok

LOGGER = logging.getLogger("labgym_launcher")


class PipOps:
    def __init__(self, runner: CommandRunner, python: str) -> None:
        self.runner = runner
        self.python = python

    def _pip(self, extra: List[str], cwd: Optional[str] = None):
        return self.runner.run(
            [self.python, "-m", "pip", "--disable-pip-version-check", *extra],
            cwd=cwd,
        )

    def list_installed(self) -> Dict[str, str]:
        LOGGER.info("reading current environment package list")
        result = self._pip(["list", "--format=json"])
        require_ok(
            result,
            PipError,
            "Could not read installed packages from the current environment.",
        )
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise PipError(
                "pip list did not return JSON. Current environment was not changed."
            ) from exc
        installed: Dict[str, str] = {}
        for item in payload:
            name = canonicalize_name(str(item.get("name", "")))
            version = str(item.get("version", "")).strip()
            if name and version:
                installed[name] = version
        return installed

    def freeze(self) -> str:
        LOGGER.info("snapshotting current environment with pip freeze")
        result = self._pip(["freeze"])
        require_ok(
            result,
            PipError,
            "Could not snapshot the current environment with pip freeze.",
        )
        return result.stdout

    def labgym_source_line(self, freeze_text: Optional[str] = None) -> Optional[str]:
        text = self.freeze() if freeze_text is None else freeze_text
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            name = stripped.split("==", 1)[0].split("@", 1)[0].strip()
            if canonicalize_name(name) == "labgym":
                return stripped
        return None

    def dry_run(self, spec: str) -> Dict[str, str]:
        LOGGER.info("comparing dependencies with pip dry-run for %s", spec)
        with tempfile.NamedTemporaryFile(
            prefix="labgym-launcher-report-",
            suffix=".json",
            delete=False,
        ) as handle:
            report_path = Path(handle.name)
        try:
            result = self._pip(
                ["install", "--dry-run", "--report", str(report_path), "--upgrade", "--", spec]
            )
            if result.returncode != 0:
                detail = (result.stderr or result.stdout).strip()
                raise DependencyPlanError(
                    "Could not compare the selected LabGym version's dependencies "
                    "against the current environment. LabGym was not launched. "
                    "Current environment was not changed.\n"
                    f"Install spec: {spec}\n{detail}"
                )
            try:
                payload = json.loads(report_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise DependencyPlanError(
                    "pip produced an unreadable dependency report. "
                    "Current environment was not changed. "
                    f"Detail: {exc}"
                ) from exc
        finally:
            try:
                report_path.unlink()
            except OSError:
                LOGGER.debug("could not delete pip report %s", report_path)
        planned: Dict[str, str] = {}
        for item in payload.get("install") or []:
            metadata = item.get("metadata") or {}
            name = canonicalize_name(str(metadata.get("name", "")))
            version = str(metadata.get("version", "")).strip()
            if name and version:
                planned[name] = version
        LOGGER.info("pip dry-run planned %s packages", len(planned))
        return planned

    def install(self, spec: str) -> None:
        LOGGER.info("installing %s", spec)
        result = self._pip(["install", "--upgrade", "--", spec])
        require_ok(result, PipError, f"pip install failed for {spec}.")

    def restore_freeze(self, freeze_path: Path) -> None:
        LOGGER.info("restoring previous environment snapshot from %s", freeze_path)
        result = self._pip(["install", "-r", str(freeze_path)])
        require_ok(
            result,
            PipError,
            "Restoring the previous environment snapshot failed.",
        )
