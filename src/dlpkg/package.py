"""
PythonPackage: a facade over a package under development that reads and writes its name,
version, authors and source roots through pyproject.toml, falling back to __init__.py's
__version__ where pyproject.toml has none.
"""
from __future__ import annotations

import logging
from pathlib import Path

from dlpkg.tomlutil import PyProjectToml
from dlpkg.versioning import read_init_version, write_init_version

logger = logging.getLogger(__name__)

PROJECT_FILE = "pyproject.toml"


class PythonPackage:
    def __init__(self, path: Path | str):
        self._root_dir = Path(path).resolve()
        if not self._root_dir.exists():
            raise FileNotFoundError(f"Package root directory does not exist: {self._root_dir}")
        self._config_file = self._open_project_file()

    def _open_project_file(self) -> PyProjectToml | None:
        path = self._root_dir / PROJECT_FILE
        if path.is_file():
            return PyProjectToml.open(path)
        logger.warning("No %s found in %s, package info will be limited.", PROJECT_FILE, self._root_dir)
        return None

    def _config(self) -> PyProjectToml:
        if self._config_file is None:
            raise RuntimeError(f"No {PROJECT_FILE} found in {self._root_dir}")
        return self._config_file

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
        return self._config().project_name

    @property
    def authors(self) -> list[str]:
        return self._config().authors

    @property
    def source_dirs(self) -> list[Path]:
        """Absolute source roots, see PyProjectToml.source_roots."""
        return self._config().source_roots

    @property
    def has_config(self) -> bool:
        return self._config_file is not None

    @property
    def version(self) -> str:
        """[project].version from pyproject.toml, else __version__ from the first __init__.py
        under a source root.

        Raises:
            RuntimeError: If no version is found in either location.
        """
        config = self._config()
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
        config = self._config()
        config.project_version = value
        config.save()
        for src_root in config.source_roots:
            try:
                write_init_version(src_root, value)
                return
            except (FileNotFoundError, AttributeError):
                continue
