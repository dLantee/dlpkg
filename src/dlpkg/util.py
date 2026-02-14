from __future__ import annotations

from dataclasses import dataclass, field, fields
import os
import shutil
import subprocess
from pathlib import Path
import tomlkit

from .versioning import SemVer

DEFAULT_SRC_DIRS = ["src", "python"]


def run(cmd: list[str], cwd: Path | None = None) -> None:
    """Runs a command in a subprocess, printing the command and working directory."""
    print(">", " ".join(cmd))
    subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=True)


def ensure_empty_dir(path: Path) -> None:
    """
    Ensures that the given path is an empty directory.
    If it exists, it will be deleted and recreated.
    """
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def copytree(src: Path, dst: Path) -> None:
    """Copies a directory tree from src to dst, removing dst first if it exists."""
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def is_git_repo(root: Path) -> bool:
    """Checks if the given root directory is a git repository by looking for a .git folder."""
    return (root / ".git").exists()


# def env_default(name: str, default: str | None = None) -> str | None:
#     """Returns the value of the environment variable `name`, or `default` if not set."""
#     v = os.environ.get(name)
#     return v if v else default


def make_read_only_recursively(path) -> None:
    """Removes write permissions for all users on the given path and its contents."""
    path = os.path.abspath(path)
    subprocess.check_call([
        "icacls",
        path,
        "/inheritance:r",  # remove inherited permissions
        "/grant:r",
        "Users:(RX)",  # Read + Execute
        "Administrators:(F)",  # Admins keep full access
        "/T",  # recursive
        "/C"  # continue on errors
    ])

