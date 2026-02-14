from __future__ import annotations

from pathlib import Path
from .util import ensure_empty_dir, run


def build_dist(repo_root: Path, out_dir: Path) -> None:
    """
    Builds sdist + wheel into out_dir using 'python -m build'.
    """
    ensure_empty_dir(out_dir)
    run(["python", "-m", "pip", "install", "--upgrade", "pip"])
    run(["python", "-m", "pip", "install", "--upgrade", "build"])
    run(["python", "-m", "build", "--outdir", str(out_dir)], cwd=repo_root)
