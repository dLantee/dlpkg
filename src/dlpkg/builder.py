from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

from dlpkg.util import ensure_empty_dir, run

WORK_DIR = "build"
PYPROJECT_FILE = "pyproject.toml"
BUILD_MODULE = "build"


class BuildError(RuntimeError):
    """A build could not start or the backend failed."""


def _artifact_stamps(out_dir: Path) -> dict[Path, int]:
    return {path: path.stat().st_mtime_ns for path in out_dir.iterdir() if path.is_file()}


def build_package(root: Path, out_dir: Path, *, sdist: bool = False, isolation: bool = True,
                  verbose: bool = False) -> list[Path]:
    """Builds `root` in `<root>/WORK_DIR`, writes the wheel (and sdist) into `out_dir` and returns
    the artifacts written by this build.

    Raises:
        BuildError: when `root` has no pyproject.toml, `build` is not installed, `out_dir` lies
            inside the work dir, or the backend fails.
    """
    root, out_dir = root.resolve(), out_dir.resolve()
    work_dir = root / WORK_DIR
    if not (root / PYPROJECT_FILE).is_file():
        raise BuildError(f"No {PYPROJECT_FILE} in {root}.")
    if importlib.util.find_spec(BUILD_MODULE) is None:
        raise BuildError(f"The '{BUILD_MODULE}' package is missing. Run: pip install {BUILD_MODULE}")
    if out_dir.is_relative_to(work_dir):
        raise BuildError(f"Output folder {out_dir} is inside {work_dir}, which is emptied on every build.")

    ensure_empty_dir(work_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    before = _artifact_stamps(out_dir)
    cmd = [sys.executable, "-m", BUILD_MODULE, "--wheel", *(["--sdist"] if sdist else []),
           "--outdir", str(out_dir), *([] if isolation else ["--no-isolation"]), str(root)]
    try:
        run(cmd, cwd=root, quiet=not verbose)
    except subprocess.CalledProcessError as exc:
        raise BuildError(f"Build failed for {root}.\n{exc.output or ''}".rstrip()) from exc
    return sorted(path for path, stamp in _artifact_stamps(out_dir).items() if before.get(path) != stamp)
