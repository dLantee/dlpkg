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


def ensure_empty_dir(path: Path) -> None:
    """Ensures that the given path is an empty directory, deleting and recreating it if it exists."""
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def make_read_only_recursively(path: Path) -> None:
    """Removes write permissions for regular users on the given path and its contents.
    Windows only: shells out to icacls."""
    run(["icacls", str(path.resolve()), *_READ_ONLY_ACL_ARGS])
