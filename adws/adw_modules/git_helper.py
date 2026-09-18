"""Low-level git operations for code phases. All low-level logic lives in adw_modules."""

from __future__ import annotations

import subprocess
from pathlib import Path


def _git(*args: str) -> str:
    result = subprocess.run(["git", *args], capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def current_branch() -> str:
    return _git("rev-parse", "--abbrev-ref", "HEAD")


def create_branch(name: str) -> str:
    _git("checkout", "-b", name)
    return name


def is_repo() -> bool:
    result = subprocess.run(["git", "rev-parse", "--git-dir"],
                            capture_output=True, text=True)
    return result.returncode == 0


def repo_root() -> Path:
    """Absolute root of the codebase — where agents are spawned to work.

    The git toplevel when there is one, else the process cwd (ADWs run fine in a
    non-git dir; only a commit phase requires a repo). Always absolute, so it is
    safe to hand to a subprocess regardless of where the ADW was launched from.
    """
    if is_repo():
        return Path(_git("rev-parse", "--show-toplevel")).resolve()
    return Path.cwd().resolve()


def _require_repo() -> None:
    if not is_repo():
        raise RuntimeError(
            "not a git repository — a commit phase needs one. Run `git init` in the "
            "repo root (and make a first commit) before running an ADW that commits.")


def commit_all(message: str) -> str:
    """Stage the whole working tree and commit it. Returns the new short sha.

    Prefer `commit_reported`: this sweeps in every untracked file in the repo,
    reported or not — a stray `node_modules/` or scratch doc lands in the
    agent's commit under the agent's message.
    """
    _require_repo()
    _git("add", "-A")
    if not _git("status", "--porcelain"):
        raise RuntimeError("nothing to commit — the preceding phases changed no files")
    _git("commit", "-m", message)
    return _git("rev-parse", "--short", "HEAD")


def reported_paths(*envelopes) -> list[str]:
    """Every repo path the given envelopes claim to have produced or changed.

    Reads the fields each output type carries — `changed_files` (builder),
    `artifacts` (everyone), `document_path` / `documented_files` (documenter) —
    so a commit phase can hand over whatever agents ran before it without
    knowing their types. Runtime artifacts under data_dir are gitignored and
    fall out naturally at staging time.
    """
    paths: list[str] = []
    for envelope in envelopes:
        if envelope is None:
            continue
        paths += list(getattr(envelope, "changed_files", []) or [])
        paths += list(getattr(envelope, "artifacts", []) or [])
        paths += list(getattr(envelope, "documented_files", []) or [])
        document_path = getattr(envelope, "document_path", "")
        if document_path:
            paths.append(document_path)
    return _relative(paths)


def _relative(paths: list[str]) -> list[str]:
    """Normalise to repo-relative POSIX paths; drop anything outside the repo."""
    root = repo_root()
    out: list[str] = []
    for raw in paths:
        if not raw:
            continue
        path = Path(raw)
        if path.is_absolute():
            try:
                path = path.resolve().relative_to(root)
            except ValueError:
                continue
        out.append(path.as_posix().rstrip("/"))
    return out


def _covered(status_path: str, reported: list[str]) -> bool:
    """A dirty path is staged when a reported path names it or a directory above it."""
    return any(status_path == r or status_path.startswith(r + "/") for r in reported)


def commit_reported(message: str, *envelopes) -> tuple[str, list[str]]:
    """Stage only the dirty paths the envelopes reported, then commit.

    Returns `(short_sha, left_behind)`, where `left_behind` is every dirty path
    nobody reported — still in the working tree, deliberately uncommitted, so
    the phase can log it and the engineer can see what the agent forgot to
    claim (or what was never the agent's to begin with).
    """
    _require_repo()
    reported = reported_paths(*envelopes)
    dirty = changed_files()
    to_stage = [path for path in dirty if _covered(path, reported)]
    left_behind = [path for path in dirty if path not in to_stage]
    if not to_stage:
        raise RuntimeError(
            "nothing to commit — no reported file is dirty. "
            f"reported={reported or '[]'}, dirty={dirty or '[]'}")
    # `-A` with a pathspec stages deletions and renames within it, not just adds.
    _git("add", "-A", "--", *to_stage)
    _git("commit", "-m", message)
    return _git("rev-parse", "--short", "HEAD"), left_behind


def changed_files() -> list[str]:
    """Every dirty path: modified, added, deleted, or untracked (respecting .gitignore).

    `-z` gives raw NUL-separated paths — the default output octal-escapes
    non-ASCII names, which would hide every `数据.json` from the commit.
    """
    result = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all", "-z"],
                            capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"git status failed: {result.stderr.strip()}")
    entries = result.stdout.split("\0")
    paths = []
    i = 0
    while i < len(entries):
        entry = entries[i]
        i += 1
        if not entry:
            continue
        paths.append(entry[3:])
        if entry[0] in "RC":            # rename/copy: the next entry is the source path
            i += 1
    return paths


# ── diff plumbing (composed into a ChangeSet by documentation.py) ────────────

def ref_exists(ref: str) -> bool:
    """True when `ref` resolves to a commit. Never raises — this is a question."""
    result = subprocess.run(["git", "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"],
                            capture_output=True, text=True)
    return result.returncode == 0


def rev(ref: str = "HEAD") -> str:
    return _git("rev-parse", ref)


def short_sha(ref: str = "HEAD") -> str:
    return _git("rev-parse", "--short", ref)


def merge_base(ref: str, other: str = "HEAD") -> str:
    """The commit where `ref` and `other` diverged — the honest base of a branch.

    On the base branch itself this returns HEAD, which makes the diff exactly
    "what is not committed yet". Off it, the diff is the whole branch plus the
    working tree. One command covers both cases, so no ADW has to branch on it.
    """
    return _git("merge-base", ref, other)


def is_dirty() -> bool:
    return bool(_git("status", "--porcelain"))


def untracked_files() -> list[str]:
    out = _git("ls-files", "--others", "--exclude-standard")
    return [line for line in out.splitlines() if line]


def diff_files(base: str) -> list[str]:
    """Tracked files that differ between `base` and the working tree."""
    out = _git("diff", "--name-only", base)
    return [line for line in out.splitlines() if line]


def diff_stat(base: str) -> str:
    return _git("diff", "--stat", base)


def diff_counts(base: str) -> tuple[int, int]:
    """(insertions, deletions) across the diff. Binary files count as neither."""
    insertions = deletions = 0
    for line in _git("diff", "--numstat", base).splitlines():
        added, removed, *_ = line.split("\t")
        if added.isdigit():
            insertions += int(added)
        if removed.isdigit():
            deletions += int(removed)
    return insertions, deletions


def diff_text(base: str) -> str:
    return _git("diff", base)
