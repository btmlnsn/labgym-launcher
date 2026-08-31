import logging
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from labgym_launcher.constants import (
    CANONICAL_SOURCE,
    FULL_HASH_PATTERN,
    HASH_PATTERN,
    SOURCE_PATTERN,
)
from labgym_launcher.errors import (
    AmbiguousHashError,
    GitError,
    InvalidHashError,
    InvalidSourceError,
    MissingHashError,
    UnresolvedHashError,
)
from labgym_launcher.models import CommitMetadata
from labgym_launcher.runner import CommandRunner
from labgym_launcher.support import require_ok

LOGGER = logging.getLogger("labgym_launcher")


def github_url(source_repo: str) -> str:
    return "https://github.com/%s.git" % source_repo


def normalize_hash_input(value: str) -> str:
    return value.strip()


def looks_like_source_repo(value: str) -> bool:
    return bool(SOURCE_PATTERN.fullmatch(value.strip()))


def validate_source_repo(value: str) -> str:
    spec = value.strip()
    if (
        not spec
        or spec.lower().endswith(".git")
        or not SOURCE_PATTERN.fullmatch(spec)
    ):
        raise InvalidSourceError(
            "Source repo %r is not a GitHub source of the form username/repo-name. "
            "Current environment was not changed." % (value,)
        )
    return spec


def validate_hash_format(value: str) -> str:
    spec = normalize_hash_input(value)
    if not spec or not HASH_PATTERN.fullmatch(spec):
        raise InvalidHashError(
            "Selected commit %r is not a git commit hash. "
            "Enter a full hash or a unique short hash (hex only). "
            "Branch names, tags, and other refs are not accepted. "
            "Current environment was not changed." % (value,)
        )
    return spec


def parse_demo_request(
    tokens: Sequence[str],
    default_source: str = CANONICAL_SOURCE,
) -> Tuple[str, str]:
    parts = [part.strip() for part in tokens if part.strip()]
    if not parts:
        raise InvalidHashError(
            "A selected commit hash is required. "
            "Usage: demo [username/repo-name] <commit>. "
            "Current environment was not changed."
        )
    if len(parts) == 1:
        token = parts[0]
        if looks_like_source_repo(token):
            raise InvalidHashError(
                "Received source repo %r without a commit hash. "
                "Usage: demo [username/repo-name] <commit>. "
                "Current environment was not changed." % (token,)
            )
        return default_source, validate_hash_format(token)
    if len(parts) == 2:
        source = validate_source_repo(parts[0])
        commit = validate_hash_format(parts[1])
        return source, commit
    raise InvalidSourceError(
        "Selected commit accepts [username/repo-name] <commit> only. "
        "Received extra arguments %s. Current environment was not changed."
        % (parts,)
    )


def resolve_commit(
    runner: CommandRunner,
    repo: Path,
    spec: str,
    source_repo: str,
) -> str:
    validated = validate_hash_format(spec)
    LOGGER.info("resolving commit hash %s in %s", validated, source_repo)
    result = runner.run(
        ["git", "rev-parse", "--verify", "%s^{commit}" % validated],
        cwd=str(repo),
    )
    combined = "%s\n%s" % (result.stderr, result.stdout)
    if result.returncode != 0:
        if "ambiguous" in combined.lower():
            raise AmbiguousHashError(
                "Commit hash %r is ambiguous in %s. "
                "Use a longer unique prefix or the full hash. "
                "Current environment was not changed. "
                "git: %s" % (validated, source_repo, combined.strip())
            )
        raise MissingHashError(
            "Commit hash %r does not resolve to a commit in %s. "
            "Current environment was not changed. "
            "git: %s" % (validated, source_repo, combined.strip())
        )
    full = result.stdout.strip().lower()
    if not FULL_HASH_PATTERN.fullmatch(full):
        raise UnresolvedHashError(
            "Commit hash %r did not resolve to a full commit SHA in %s. "
            "git returned %r. Current environment was not changed."
            % (validated, source_repo, result.stdout)
        )
    LOGGER.info("resolved %s in %s to %s", validated, source_repo, full)
    return full


def resolve_release_tag(
    runner: CommandRunner,
    repo: Path,
    version: str,
    source_repo: str,
) -> Tuple[str, str]:
    candidates = ["v%s" % version, version]
    details: List[str] = []
    for tag in candidates:
        LOGGER.info("resolving official release tag %s in %s", tag, source_repo)
        result = runner.run(
            ["git", "rev-parse", "--verify", "%s^{commit}" % tag],
            cwd=str(repo),
        )
        if result.returncode == 0:
            full = result.stdout.strip().lower()
            if FULL_HASH_PATTERN.fullmatch(full):
                LOGGER.info("resolved tag %s to %s", tag, full)
                return tag, full
            details.append("%s -> %r" % (tag, result.stdout.strip()))
            continue
        details.append("%s -> %s" % (tag, (result.stderr or result.stdout).strip()))
    raise UnresolvedHashError(
        "Official LabGym PyPI release %s has no matching git tag in %s "
        "(tried %s). Current environment was not changed. git: %s"
        % (version, source_repo, ", ".join(candidates), " | ".join(details))
    )


def describe_commit(
    runner: CommandRunner,
    repo: Path,
    revision: str,
) -> CommitMetadata:
    """Read commit subject and source-branch provenance from remote-tracking refs.

    Local detached HEAD is an implementation detail and is not used as the
    branch label. Missing provenance is returned as None.
    """
    return CommitMetadata(
        commit=revision,
        branch_name=_source_branch_from_remote_refs(runner, repo, revision),
        subject=_commit_subject(runner, repo, revision),
    )


def _commit_subject(
    runner: CommandRunner,
    repo: Path,
    revision: str,
) -> Optional[str]:
    result = runner.run(
        ["git", "log", "-1", "--format=%s", revision],
        cwd=str(repo),
    )
    if result.returncode != 0:
        return None
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return lines[0] if lines else None


def _source_branch_from_remote_refs(
    runner: CommandRunner,
    repo: Path,
    revision: str,
) -> Optional[str]:
    default_branch = _origin_default_branch(runner, repo)
    for selector in ("--points-at", "--contains"):
        names = _remote_ref_names(runner, repo, selector, revision)
        chosen = _choose_source_branch(names, default_branch)
        if chosen:
            return chosen
    return None


def _remote_ref_names(
    runner: CommandRunner,
    repo: Path,
    selector: str,
    revision: str,
) -> List[str]:
    result = runner.run(
        [
            "git",
            "for-each-ref",
            "--format=%(refname:short)",
            selector,
            revision,
            "refs/remotes",
        ],
        cwd=str(repo),
    )
    if result.returncode != 0:
        return []
    names: List[str] = []
    for line in result.stdout.splitlines():
        name = line.strip()
        if not name or name in {"HEAD", "origin/HEAD"}:
            continue
        names.append(name)
    return names


def _origin_default_branch(runner: CommandRunner, repo: Path) -> Optional[str]:
    result = runner.run(
        ["git", "symbolic-ref", "--quiet", "refs/remotes/origin/HEAD"],
        cwd=str(repo),
    )
    if result.returncode != 0:
        return None
    ref = result.stdout.strip()
    prefix = "refs/remotes/origin/"
    if ref.startswith(prefix):
        return ref[len(prefix) :] or None
    return _display_remote_branch(ref)


def _choose_source_branch(
    names: List[str],
    default_branch: Optional[str],
) -> Optional[str]:
    cleaned = []
    for name in names:
        display = _display_remote_branch(name)
        if display and display not in cleaned:
            cleaned.append(display)
    if not cleaned:
        return None
    if default_branch and default_branch in cleaned:
        return default_branch
    return cleaned[0]


def _display_remote_branch(name: str) -> Optional[str]:
    text = name.strip()
    if not text or text in {"HEAD", "origin/HEAD"}:
        return None
    if text.startswith("origin/"):
        text = text[len("origin/") :]
    return text or None


def current_head(runner: CommandRunner, repo: Path) -> Optional[str]:
    git_dir = Path(repo) / ".git"
    if not git_dir.exists():
        return None
    result = runner.run(["git", "rev-parse", "--verify", "HEAD"], cwd=str(repo))
    if result.returncode != 0:
        return None
    full = result.stdout.strip().lower()
    if not FULL_HASH_PATTERN.fullmatch(full):
        return None
    return full


def origin_matches(runner: CommandRunner, repo: Path, url: str) -> bool:
    result = runner.run(["git", "remote", "get-url", "origin"], cwd=str(repo))
    if result.returncode != 0:
        return False
    return _normalize_remote(result.stdout) == _normalize_remote(url)


def origin_url(runner: CommandRunner, repo: Path) -> str:
    result = runner.run(["git", "remote", "get-url", "origin"], cwd=str(repo))
    require_ok(
        result,
        GitError,
        "Could not read origin for launcher checkout %s. "
        "Current environment was not changed." % repo,
    )
    return result.stdout.strip()


def checkout_revision(runner: CommandRunner, repo: Path, revision: str) -> None:
    LOGGER.info("checking out %s in %s", revision, repo)
    checked = runner.run(
        ["git", "checkout", "--detach", "--force", revision],
        cwd=str(repo),
    )
    require_ok(
        checked,
        GitError,
        "Could not check out %s in launcher working tree %s. "
        "Current environment was not changed." % (revision, repo),
    )
    cleaned = runner.run(["git", "clean", "-fd"], cwd=str(repo))
    require_ok(
        cleaned,
        GitError,
        "Could not clean launcher working tree %s after checkout. "
        "Current environment was not changed." % repo,
    )


def retarget_working_tree(
    runner: CommandRunner,
    path: Path,
    url: str,
    label: str,
) -> None:
    """Reuse one persistent working tree. Never clone a new directory per commit."""
    path.parent.mkdir(parents=True, exist_ok=True)
    git_dir = path / ".git"
    if not git_dir.exists():
        if path.exists() and any(path.iterdir()):
            raise GitError(
                "Launcher %s checkout %s exists but is not a git repository. "
                "Current environment was not changed." % (label, path)
            )
        LOGGER.info("cloning %s into persistent %s checkout %s", url, label, path)
        cloned = runner.run(["git", "clone", "--", url, str(path)])
        require_ok(
            cloned,
            GitError,
            "Could not clone %s into persistent %s checkout %s. "
            "Current environment was not changed." % (url, label, path),
        )
        return
    current = origin_url(runner, path)
    if _normalize_remote(current) != _normalize_remote(url):
        LOGGER.info(
            "retargeting persistent %s checkout %s from %s to %s",
            label,
            path,
            current,
            url,
        )
        updated = runner.run(
            ["git", "remote", "set-url", "origin", url],
            cwd=str(path),
        )
        require_ok(
            updated,
            GitError,
            "Could not retarget persistent %s checkout %s to %s. "
            "Current environment was not changed." % (label, path, url),
        )
    LOGGER.info("fetching %s in persistent %s checkout", url, label)
    fetched = runner.run(
        ["git", "fetch", "--tags", "--prune", "--", "origin"],
        cwd=str(path),
    )
    require_ok(
        fetched,
        GitError,
        "Could not fetch %s in persistent %s checkout %s. "
        "Current environment was not changed." % (url, label, path),
    )


def _normalize_remote(url: str) -> str:
    return url.strip().rstrip("/").lower()
