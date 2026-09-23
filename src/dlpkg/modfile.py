"""
Maya module files: <name>.mod on MAYA_MODULE_PATH pointing at one published version folder.
Maya reads `+ <name> <version> <path>` and adds <path> (plus PYTHONPATH lines) at startup.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

MAYA_MODULE_PATH_ENV = "MAYA_MODULE_PATH"
MOD_SUFFIX = ".mod"
# pip --target puts the package right inside the version folder, so the module root is on PYTHONPATH.
_PYTHONPATH_LINE = "PYTHONPATH +:= ."
_MODULE_LINE_RE = re.compile(r"^\+\s+(?P<name>\S+)\s+(?P<version>\S+)\s+(?P<path>.+?)\s*$")


def first_maya_module_dir() -> Path | None:
    """The first existing directory on MAYA_MODULE_PATH, or None when there is none."""
    for raw in os.environ.get(MAYA_MODULE_PATH_ENV, "").split(os.pathsep):
        candidate = Path(raw.strip().strip('"'))
        if raw.strip() and candidate.is_dir():
            return candidate
    return None


def mod_file_path(mod_dir: Path, name: str) -> Path:
    return mod_dir / f"{name}{MOD_SUFFIX}"


def write_mod_file(mod_dir: Path, name: str, version: str, install_dir: Path) -> Path:
    """Writes (or overwrites) <mod_dir>/<name>.mod pointing at install_dir."""
    mod_path = mod_file_path(mod_dir, name)
    lines = [f"+ {name} {version} {install_dir.resolve().as_posix()}", _PYTHONPATH_LINE]
    mod_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return mod_path


def read_mod_target(mod_path: Path) -> Path | None:
    """The install dir a .mod file points at, or None when the file is missing or has no module line."""
    if not mod_path.is_file():
        return None
    for line in mod_path.read_text(encoding="utf-8").splitlines():
        m = _MODULE_LINE_RE.match(line)
        if m:
            return Path(m.group("path")).resolve()
    return None
