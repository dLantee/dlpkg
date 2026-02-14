"""
Installer logic: copying source files into versioned install folders,
and writing .mod files for Maya.

Expects pyproject.toml with setuptools configuration to determine source roots.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import shutil

from dlpkg.util import ensure_empty_dir, make_read_only_recursively, run


@dataclass(frozen=True)
class InstallSpec:
    """Specification for an installation location and versioning.
    """
    name: str                 # package name
    version: str              # x.y.z (base)
    channel: str              # "rel" or "dev"
    target_root: Path         # where installs go (e.g. publishes/)

    def folder_name(self) -> str:
        """ Creates folder name based on channel and version. """
        return f"{self.channel}-{self.version}"


def install_wheel(wheel_path: Path, dst: Path, override=False, write_mod_file=False) -> Path:
    """
    Publishes the given source folder to the target location based on install_spec.
    Copies src_dir to target_root/name/folder_name()

    Args:
        - src_dir: Path to source folder to publish (e.g. src/mypkg)
        - install_spec: InstallSpec with name, version, channel, target_root, etc.
        - override: If True, will delete existing target folder if it exists. If False, will raise FileExistsError if target folder already exists.
        - write_mod_file: If True, will write a .mod file for Maya with PYTHONPATH entries for source roots.
    Returns:
        - Path to the published folder (e.g. publishes/mypkg/dev-1.2.3-devN+branch.sha/)
    """

    # -- resolve target folder

    if override:
        try:
            ensure_empty_dir(dst)
        except PermissionError as e:
            e.args = (f"Cannot override installed packages. Access is denied: {dst!r}", )
            raise e
    elif dst.exists():
        raise FileExistsError(f"Target folder already exists: {dst!r}")

    run(["python", "-m", "pip", "install", wheel_path.as_posix(), "--target", dst.as_posix()])

    make_read_only_recursively(dst)

    # if write_mod_file:
    #     mod_path = _write_mod_file(
    #         module_name=install_spec.name,
    #         module_version=install_spec.version,
    #         install_dir=dst,
    #         python_paths=["."],
    #     )
    #     print(f"Wrote .mod: {mod_path}")

    return dst


def _first_maya_module_dir() -> Path:
    """
    Chooses the first existing directory from MAYA_MODULE_PATH.
    """
    raw = os.environ.get("MAYA_MODULE_PATH", "")
    if not raw:
        raise RuntimeError("MAYA_MODULE_PATH is not set, cannot write .mod file.")

    for p in raw.split(os.pathsep):
        p = p.strip().strip('"')
        if not p:
            continue
        d = Path(p)
        if d.exists() and d.is_dir():
            return d

    raise RuntimeError("No existing directory found in MAYA_MODULE_PATH.")


def _write_mod_file(module_name: str, module_version: str, install_dir: Path, python_paths: list[str]) -> Path:
    """
    Writes <module_name>.mod into the first folder on MAYA_MODULE_PATH.
    Adds PYTHONPATH entries based on pyproject-derived source roots.
    """
    mod_dir = _first_maya_module_dir()
    mod_path = mod_dir / f"{module_name}.mod"

    lines = []
    # Basic module line: + <name> <version> <absolute_path>
    lines.append(f"+ {module_name} {module_version} {install_dir.as_posix()}")
    # Add python paths relative to module root
    for rel in python_paths:
        lines.append(f"PYTHONPATH +:= {rel}")

    mod_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return mod_path


