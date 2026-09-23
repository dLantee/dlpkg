from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

# icacls arguments that strip inherited ACLs and leave Users read-only, Administrators full.
_READ_ONLY_ACL_ARGS = ["/inheritance:r", "/grant:r", "Users:(RX)", "Administrators:(F)", "/T", "/C"]


def run(cmd: list[str], cwd: Path | None = None) -> None:
    """Runs a command in a subprocess, printing the command first."""
    print(">", " ".join(cmd))
    subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=True)


def git(args: list[str], cwd: Path) -> str:
    """Runs git in `cwd` and returns its stripped stdout.

    Raises:
        subprocess.CalledProcessError: when git exits non-zero.
    """
    result = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, check=True)
    return result.stdout.strip()


def git_short_hash(path: Path) -> str | None:
    """Short hash of HEAD for the git repository containing `path`, or None when there is none."""
    cwd = path if path.is_dir() else path.parent
    try:
        return git(["rev-parse", "--short", "HEAD"], cwd) or None
    except (OSError, subprocess.CalledProcessError):
        return None


def git_is_clean(path: Path) -> bool:
    """True when no tracked file under `path` has uncommitted changes. Untracked files are ignored."""
    return not git(["status", "--porcelain", "--untracked-files=no", "."], path)


def ensure_empty_dir(path: Path) -> None:
    """Ensures that the given path is an empty directory, deleting and recreating it if it exists."""
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def make_read_only_recursively(path: Path) -> None:
    """Removes write permissions for regular users on the given path and its contents.
    Windows only: shells out to icacls."""
    run(["icacls", str(path.resolve()), *_READ_ONLY_ACL_ARGS])
