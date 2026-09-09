# LabGym Launcher

LabGym Launcher is a team/demo companion for switching a local LabGym
environment between the latest official LabGym PyPI release and a selected
GitHub commit. It is **not LabGym**. It does not replace LabGym, publish
LabGym, or speak for the LabGym project.

This repository is the standalone launcher package (`labgym-launcher`).
The current milestone is **0.2.0**. Internal rollout is a GitHub tag install,
not PyPI, and not a desktop installer.

## Install

Requires Python 3.9 or newer, Git on `PATH`, and an existing Python
environment where you already run LabGym (or are prepared to install it).
The GUI extra installs wxPython.

The expected internal tag is `v0.2.0`. That tag is not assumed to exist
yet. Create and push that tag before sending the install command to
teammates.

```bash
python -m pip install "labgym-launcher[gui] @ git+https://github.com/btmlnsn/labgym-launcher.git@v0.2.0"
```

CLI-only install (no wxPython):

```bash
python -m pip install "labgym-launcher @ git+https://github.com/btmlnsn/labgym-launcher.git@v0.2.0"
```

PyPI is not a distribution path for LabGym Launcher. A later public
package would need a separate license and distribution decision, and
would still have to stay clearly separate from LabGym itself.

The GitHub tag install command is for authorized LabGym teammates; public
repository visibility is not a general permission to use or redistribute
the launcher.

## Start

```bash
labgym-launcher
```

That opens the GUI. Equivalent: `labgym-launcher-gui` or
`python -m labgym_launcher`.

CLI fallback:

```bash
labgym-launcher --cli status
labgym-launcher-cli status
```

## Concepts

- **Official Release** — latest LabGym release on PyPI.
- **Selected Commit** — a GitHub source (`username/repo-name`) plus a commit
  hash. Omit the source to use the canonical LabGym repo, `umyelab/LabGym`.
- There is no manifest or curated allowlist. Any resolvable public GitHub
  source in `username/repo-name` form may be requested.
- The launcher owns two persistent working trees under
  `~/.labgym-launcher/worktrees/`: Official Release (`home`) and Selected
  Commit (`demo`).
- One Official Release session and one Selected Commit session may run at
  the same time. A second session of the same class is blocked. Closed
  sessions are reaped.
- Remembered commits can carry optional aliases.

## GUI workflow

1. Start `labgym-launcher`.
2. Review **Current State**.
3. **Launch Official Release** installs (if needed) and starts the latest
   LabGym PyPI release.
4. For a commit: enter `username/repo-name` (or leave the default) and a
   full or uniquely resolvable short hash, then **Launch Selected Commit**.
5. Confirm the dependency plan before any install proceeds.
6. Use **Remembered Commits** to reload a prior target or edit an alias
   (**Load Target**, **Edit Alias**).
7. **Restore Official Release** returns the environment to the latest
   Official Release without launching LabGym.
8. **Refresh** reloads status.

## CLI fallback

```bash
labgym-launcher --cli home
labgym-launcher --cli demo abc1234
labgym-launcher --cli demo username/repo-name abc1234
labgym-launcher --cli status
labgym-launcher --cli rollback
```

`home` launches Official Release. `demo` launches a Selected Commit.
`rollback` restores Official Release and does **not** launch LabGym
(same action as **Restore Official Release** in the GUI). Each install
path prints a dependency plan and asks `Proceed with installation? [y/N]`.

## Restore Official Release

GUI: **Restore Official Release**.

CLI:

```bash
labgym-launcher --cli rollback
```

Restore installs the latest Official Release and leaves LabGym unlaunched.
Failed installs are intended to leave the current environment as unchanged
as possible. Restore remains available after a failed Selected Commit
install.

## Data directory

Default: `~/.labgym-launcher/`

| Path | Role |
| --- | --- |
| `worktrees/home` | Official Release working tree |
| `worktrees/demo` | Selected Commit working tree |
| `state.json` | launcher state |
| `sessions.json` | live session registry |
| `launcher.log` | log file |

Override the root with `LABGYM_LAUNCHER_HOME`.

## Safety model

Dependencies are compared before install. The GUI confirmation dialog and
the CLI `y/N` prompt both require explicit approval. Nothing is installed
until you confirm. There is no selected-commit allowlist; you are choosing
the GitHub source and hash. Duplicate sessions of the same class are
blocked. Failed installs try not to replace a working environment.

## Requirements

- Python 3.9 or newer (CI runs 3.10).
- Git on `PATH`.
- An existing LabGym-capable Python environment (the launcher switches
  LabGym in the environment you install it into).
- GUI: wxPython 4.2 or newer via the `[gui]` extra.
- Network access to PyPI (Official Release metadata) and GitHub (commit
  resolution and clone/fetch).

## Platforms

GitHub Actions CI is green on Ubuntu 22.04, macOS, and Windows (Python
3.10), including GUI tests. Linux CI installs a Ubuntu 22.04 wxPython
wheel; other Linux distros may need a local wxPython build.

## Current limitations

- Pre-1.0 team/demo tool, not a general LabGym installer.
- Not published to PyPI; no standalone desktop installers.
- Hash must resolve uniquely in the chosen GitHub repo.
- One session per class (Official Release, Selected Commit).
- Restore / CLI `rollback` does not launch LabGym.
- wxPython on Linux is the most common GUI install friction.

## Troubleshooting

**GUI does not start / asks for wxPython**

Install the GUI extra into the same environment:

```bash
python -m pip install "labgym-launcher[gui] @ git+https://github.com/btmlnsn/labgym-launcher.git@v0.2.0"
```

**`git` not found**

Install Git and confirm `git` works in the same shell as the launcher.

**Commit hash is invalid or ambiguous**

Use a longer prefix or the full 40-character hash. The hash must exist
and resolve uniquely in `username/repo-name`.

**A session is already running**

Close the existing LabGym window of that class, or use the other class.
The launcher reaps closed sessions on refresh/status.

**Install failed**

Read `~/.labgym-launcher/launcher.log`. Restore Official Release if the
environment is left on a Selected Commit you no longer want.

**Linux wxPython install fails**

Use a distro/wxPython combination that provides wheels, or install
wxPython by the method your platform documents, then reinstall the
launcher with `[gui]`.

**Need a different data directory**

Set `LABGYM_LAUNCHER_HOME` before starting the launcher.

## Screenshots

Screenshots will be added after capture from the accepted GUI. Intended
paths:

- `docs/images/launcher-main.png`
- `docs/images/launcher-confirmation.png`
- `docs/images/launcher-remembered-commits.png`

## License

LabGym Launcher is source-available, not open source. It is not
MIT-licensed and is not OSI-approved. The current grant is limited
internal LabGym team evaluation and development: no redistribution,
no commercial use, and no sublicensing, unless written permission is
granted by an authorized project maintainer or copyright holder. This
software is not LabGym. See [LICENSE](LICENSE).
