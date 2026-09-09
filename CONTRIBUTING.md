# Contributing to LabGym Launcher

LabGym Launcher is a standalone companion package. Keep its identity,
docs, and window chrome separate from LabGym. Do not describe this
repository as LabGym itself.

## License

This repository is source-available, not open source. See
[LICENSE](LICENSE). Do not describe it as MIT-licensed or
OSI-approved. Contributions are accepted only under the same
source-available posture unless a separate written agreement says
otherwise.

## Setup

From the repository root, in the Python environment you use for LabGym:

```bash
python -m pip install -U pip
python -m pip install -e ".[gui,test]"
```

Linux GUI extra: if `wxPython` has no wheel for your distro, install
wxPython first, then `python -m pip install -e ".[test]"`. CI on Ubuntu
22.04 uses the wxPython extras index for `wxPython==4.2.5`.

## Tests

```bash
python -m unittest discover -s tests -v
```

Linux without a display:

```bash
xvfb-run -a python -m unittest discover -s tests -v
```

The editable install is the documented setup. If you need a no-install
local check, `PYTHONPATH=src python -m unittest discover -s tests -v` is
a shortcut. It is not the primary contributor setup.

GUI tests skip only when wxPython or a display is missing.

## CI

[`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs on push to
`main`/`master` and on pull requests. Matrix: Ubuntu 22.04, macOS, Windows,
Python 3.10. Linux uses Xvfb. Keep changes green on all three.

## Agent and Git rules

Agents must not mutate Git: no stage, commit, push, pull, fetch, branch,
tag, stash, switch, restore, reset, merge, rebase, or remote/config
changes. Humans own repository history.

Markdown files require explicit approval of the proposed content and
targets before any write.

## Architecture

Backend (`LauncherBackend`) owns policy: targets, confirmation, install,
sessions, restore. GUI and CLI stay thin and call the same backend. Do
not add launcher policy only in wx code.

Keep Windows AppUserModelID `umyelab.LabGymLauncher` (not LabGym’s
`umyelab.LabGym`). Packaged icons live under
`src/labgym_launcher/assets/icons/`.

## Commit messages

Use [Conventional Commits](https://www.conventionalcommits.org/): a type
prefix, optional scope, then a short description.

Types used in this repo:

- `feat:` — user-facing capability
- `fix:` — bug fix
- `ci:` — GitHub Actions / CI
- `docs:` — README, CONTRIBUTING, comments aimed at humans
- `test:` — tests only
- `chore:` — version bumps, packaging, housekeeping

Examples:

```text
feat: remember selected-commit aliases
fix: reap closed sessions before blocking duplicates
ci: retry Ubuntu wxPython wheel install
docs: describe GitHub tag install for 0.2.0
test: cover confirmation dialog parenting
chore: bump version to 0.2.0
```

Explain why in the body when the change is not obvious from the subject.
Do not commit secrets, local data under `~/.labgym-launcher/`, or
unapproved screenshots.

## Versioning

Pre-1.0 SemVer (`0.y.z`):

- **Minor** (`0.2.0`, `0.3.0`, …): meaningful user-facing stages.
- **Patch** (`0.2.1`): fixes and polish that do not define a new stage.
- **1.0.0** is reserved for the first stable, documented distribution.

Keep `pyproject.toml`, `labgym_launcher.__version__`, and
`USER_AGENT` in `constants.py` in lockstep. Internal rollout tags use
the form `v0.2.0` (leading `v`).

## Screenshots and assets

Do not add screenshots until README text is approved and the GUI is in
the accepted state. Capture real windows; do not mock. Do not add
`![]()` image links to README until the files exist.

Intended paths:

- `docs/images/launcher-main.png`
- `docs/images/launcher-confirmation.png`
- `docs/images/launcher-remembered-commits.png`

PNG, cropped to the dialog or frame, no fake data that contradicts
current labels. Runtime icons are packaged separately; do not treat
`docs/images/` as the app icon source.
