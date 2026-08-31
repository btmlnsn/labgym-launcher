"""Default entry is the GUI; CLI is explicit via ``--cli`` or ``labgym-launcher-cli``."""

import sys
from typing import Callable, List, Optional

HELP = """usage: labgym-launcher [--cli COMMAND ...]
       labgym-launcher-gui
       labgym-launcher-cli COMMAND ...

LabGym Launcher starts the desktop GUI by default.

  labgym-launcher              open the GUI
  labgym-launcher --cli ...    run the command-line interface
  labgym-launcher-cli ...      same as --cli
  labgym-launcher-gui          open the GUI

CLI commands: home (Official Release), demo (selected commit), status, rollback.
"""


def split_cli_argv(argv: List[str]) -> Optional[List[str]]:
    if argv and argv[0] == "--cli":
        return argv[1:]
    return None


def main(
    argv: Optional[List[str]] = None,
    gui_main: Optional[Callable[[Optional[List[str]]], int]] = None,
    cli_main: Optional[Callable[[Optional[List[str]]], int]] = None,
) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    cli_argv = split_cli_argv(args)
    if cli_argv is not None:
        from labgym_launcher.cli import main as default_cli

        return (cli_main or default_cli)(cli_argv)
    if args and args[0] in {"-h", "--help"}:
        sys.stdout.write(HELP)
        return 0
    from labgym_launcher.gui import main as default_gui

    return (gui_main or default_gui)(args)


if __name__ == "__main__":
    raise SystemExit(main())
