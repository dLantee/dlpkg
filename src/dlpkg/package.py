"""
PythonPackage: a facade over a package under development that reads and writes its name,
version, authors and source roots through pyproject.toml, falling back to __init__.py's
__version__ where pyproject.toml has none.
"""
from __future__ import annotations

from pathlib import Path

from dlpkg.tomlutil import PyProjectToml
from dlpkg.versioning import read_init_version, write_init_version

PROJECT_FILE = "pyproject.toml"


def find_package_root(start: Path | str) -> Path:
    """Returns the nearest folder at or above `start` that holds pyproject.toml.

    Raises:
        FileNotFoundError: if `start` does not exist or no folder up to the drive root has pyproject.toml.
    """
    start_dir = Path(start).resolve()
    if not start_dir.is_dir():
        raise FileNotFoundError(f"Package folder does not exist: {start_dir}")
    for candidate in (start_dir, *start_dir.parents):
        if (candidate / PROJECT_FILE).is_file():
            return candidate
    raise FileNotFoundError(f"No {PROJECT_FILE} found in {start_dir} or any parent folder. "
                            "Run dlpkg inside a package, or pass its path.")


class PythonPackage:
    def __init__(self, path: Path | str):
        self._root_dir = find_package_root(path)
        self._config = PyProjectToml.open(self._root_dir / PROJECT_FILE)

    @property
    def root_dir(self) -> Path:
        """Absolute package root directory (where pyproject.toml lives)."""
        return self._root_dir

    @property
    def name(self) -> str:
        """The root folder's name."""
        return self._root_dir.name

    @property
    def project_name(self) -> str:
        """[project].name from pyproject.toml."""
        return self._config.project_name

    @property
    def authors(self) -> list[str]:
        return self._config.authors

    @property
    def source_dirs(self) -> list[Path]:
        """Absolute source roots, see PyProjectToml.source_roots."""
        return self._config.source_roots

    @property
    def version(self) -> str:
        """[project].version from pyproject.toml, else __version__ from the first __init__.py
        under a source root.

        Raises:
            RuntimeError: If no version is found in either location.
        """
        config = self._config
        try:
            return config.project_version
        except RuntimeError:
            for src_root in config.source_roots:
                try:
                    return read_init_version(src_root)
                except (FileNotFoundError, AttributeError):
                    continue
        raise RuntimeError(f"Could not find package version in {self._root_dir}")

    @version.setter
    def version(self, value: str) -> None:
        """Writes the version into pyproject.toml, and into the first __init__.py that defines
        __version__ under a source root, if there is one."""
        config = self._config
        config.project_version = value
        config.save()
        for src_root in config.source_roots:
            try:
                write_init_version(src_root, value)
                return
            except (FileNotFoundError, AttributeError):
                continue
