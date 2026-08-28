import argparse
import logging
import sys
from typing import List, Optional, TextIO

from labgym_launcher.backend import LauncherBackend
from labgym_launcher.confirm import format_confirmation, format_status
from labgym_launcher.constants import CANONICAL_SOURCE
from labgym_launcher.errors import LauncherError
from labgym_launcher.gitops import parse_demo_request
from labgym_launcher.models import Confirmation

LOGGER = logging.getLogger("labgym_launcher")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="labgym-launcher",
        description=(
            "Launch official LabGym (home) or a demo git commit. "
            "Demo source is username/repo-name; it defaults to %s. "
            "A hash may be full or short, but it must resolve uniquely in that repo. "
            "There is no demo allowlist." % CANONICAL_SOURCE
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("home", help="install and launch the latest official LabGym PyPI release")
    demo = sub.add_parser(
        "demo",
        help="install and launch LabGym at a user-entered GitHub source and commit hash",
    )
    demo.add_argument(
        "source_and_commit",
        nargs="+",
        metavar="SOURCE_OR_COMMIT",
        help=(
            "optional GitHub source as username/repo-name, then a full or unique "
            "short commit hash. If the source is omitted, %s is used."
            % CANONICAL_SOURCE
        ),
    )
    sub.add_parser("status", help="show launcher and LabGym status")
    sub.add_parser(
        "rollback",
        help="restore the latest official LabGym PyPI release without launching",
    )
    return parser


def configure_logging(backend: LauncherBackend) -> None:
    backend.data_dir.mkdir(parents=True, exist_ok=True)
    handlers: List[logging.Handler] = [logging.StreamHandler(sys.stderr)]
    try:
        handlers.append(logging.FileHandler(backend.log_path(), encoding="utf-8"))
    except OSError:
        LOGGER.warning("could not open launcher log file at %s", backend.log_path())
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=handlers,
        force=True,
    )


def prompt_approval(
    confirmation: Confirmation,
    stdin: TextIO,
    stdout: TextIO,
) -> bool:
    stdout.write(format_confirmation(confirmation))
    stdout.write("\n\nProceed with installation? [y/N] ")
    stdout.flush()
    answer = stdin.readline()
    if not answer:
        return False
    return answer.strip().lower() in {"y", "yes"}


def run_command(
    args: argparse.Namespace,
    backend: LauncherBackend,
    stdin: TextIO,
    stdout: TextIO,
) -> int:
    if args.command == "status":
        stdout.write(format_status(backend.status()) + "\n")
        return 0
    if args.command == "home":
        confirmation = backend.prepare_home()
        return _confirm_apply_launch(backend, confirmation, stdin, stdout, launch=True)
    if args.command == "demo":
        source, commit = parse_demo_request(args.source_and_commit)
        confirmation = backend.prepare_demo(commit, source_repo=source)
        return _confirm_apply_launch(backend, confirmation, stdin, stdout, launch=True)
    if args.command == "rollback":
        confirmation = backend.prepare_rollback()
        return _confirm_apply_launch(backend, confirmation, stdin, stdout, launch=False)
    raise LauncherError("Unknown command %r." % args.command)


def _confirm_apply_launch(
    backend: LauncherBackend,
    confirmation: Confirmation,
    stdin: TextIO,
    stdout: TextIO,
    launch: bool,
) -> int:
    if confirmation.needs_install:
        if not prompt_approval(confirmation, stdin, stdout):
            stdout.write(
                "\nInstallation cancelled. Current environment was not changed.\n"
            )
            return 0
        backend.apply(confirmation, approved=True)
        stdout.write("Installation complete.\n")
    else:
        stdout.write(format_confirmation(confirmation) + "\n")
        stdout.write("No dependency installation is required.\n")
        backend.apply(confirmation, approved=True)
    if launch:
        backend.launch()
    else:
        stdout.write("Rollback complete. LabGym was not launched.\n")
    return 0


def main(
    argv: Optional[List[str]] = None,
    backend: Optional[LauncherBackend] = None,
    stdin: Optional[TextIO] = None,
    stdout: Optional[TextIO] = None,
) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    active_backend = backend or LauncherBackend()
    if backend is None:
        configure_logging(active_backend)
    in_stream = stdin if stdin is not None else sys.stdin
    out_stream = stdout if stdout is not None else sys.stdout
    try:
        return run_command(args, active_backend, in_stream, out_stream)
    except LauncherError as exc:
        LOGGER.info("launcher error: %s", exc)
        sys.stderr.write(str(exc) + "\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
