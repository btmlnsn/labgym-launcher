import logging
import subprocess
from dataclasses import dataclass
from typing import Optional, Sequence

LOGGER = logging.getLogger("labgym_launcher")


@dataclass(frozen=True)
class CommandResult:
    args: tuple
    returncode: int
    stdout: str
    stderr: str


class CommandRunner:
    def run(
        self,
        args: Sequence[str],
        cwd: Optional[str] = None,
        capture: bool = True,
    ) -> CommandResult:
        argv = [str(part) for part in args]
        LOGGER.debug("command %s cwd=%s", argv, cwd)
        completed = subprocess.run(
            argv,
            cwd=cwd,
            capture_output=capture,
            text=True,
            check=False,
        )
        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        LOGGER.debug("command exit %s", completed.returncode)
        if completed.returncode != 0:
            detail = (stderr or stdout).strip()
            LOGGER.info("command failed: %s", detail[:2000])
        return CommandResult(
            args=tuple(argv),
            returncode=completed.returncode,
            stdout=stdout,
            stderr=stderr,
        )

    def start(
        self,
        args: Sequence[str],
        cwd: Optional[str] = None,
    ) -> subprocess.Popen:
        argv = [str(part) for part in args]
        LOGGER.debug("start %s cwd=%s", argv, cwd)
        return subprocess.Popen(argv, cwd=cwd)
