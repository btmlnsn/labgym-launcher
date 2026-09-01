import re

PYPI_PROJECT = "LabGym"
CANONICAL_SOURCE = "umyelab/LabGym"
PYPI_JSON_URL = "https://pypi.org/pypi/LabGym/json"
LABGYM_MODULE = "LabGym"
ENV_HOME = "LABGYM_LAUNCHER_HOME"
DATA_DIR_NAME = ".labgym-launcher"
WORKTREES_DIRNAME = "worktrees"
HOME_WORKTREE = "home"
DEMO_WORKTREE = "demo"
STATE_FILENAME = "state.json"
SESSIONS_FILENAME = "sessions.json"
LOG_FILENAME = "launcher.log"
FREEZE_FILENAME = "pre_install_freeze.txt"
STATE_VERSION = 1
HOME = "home"
DEMO = "demo"
ROLLBACK = "rollback"
OFFICIAL_RELEASE_LABEL = "Official Release"
SELECTED_COMMIT_LABEL = "selected commit"
SELECTED_COMMIT_BUTTON_LABEL = "Selected Commit"
RESTORE_OFFICIAL_LABEL = "Restore Official Release"
SOURCE_BRANCH_UNKNOWN_LABEL = "source branch unknown"
GITHUB_BRANCHES_WHERE_HEAD_URL = (
    "https://api.github.com/repos/%s/commits/%s/branches-where-head"
)
USER_AGENT = "labgym-launcher/0.1.0"
HASH_PATTERN = re.compile(r"^[0-9a-fA-F]{4,40}$")
FULL_HASH_PATTERN = re.compile(r"^[0-9a-fA-F]{40}$")
SOURCE_PATTERN = re.compile(r"^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$")
