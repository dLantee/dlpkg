"""
Module that provides information about the package,
such as its root directory, pyproject.toml location, etc...
"""
from pathlib import Path

from dlpkg.tomlutil import PyProjectToml
from dlpkg.versioning import init_version


def get_source_root() -> Path | None:
    """Returns the package root directory (where __init__.py is) if found, else None."""
    # Look for src/*/__init__.py
    for src in Path("src").glob("*"):
        if (src / "__init__.py").exists():
            return src
    return None


def get_pyproject_root() -> Path | None:
    """Returns the directory containing pyproject.toml if found, else None."""
    for p in Path(".").glob("**/pyproject.toml"):
        return p.parent
    return None


class PythonPackage(object):
    """
    Provides information about a Python package including name,
    version, and author. It tries to read this information from pyproject.toml first,
    and falls back to other methods if not found.
    """

    def __init__(self, path: Path | str):
        self._root_dir = Path(path).resolve()
        if not self._root_dir.exists():
            raise FileNotFoundError(f"Package root directory does not exist: {self._root_dir}")

        self._config_file = self._search_project_file()

    @property
    def name(self) -> str:
        """Get the package name."""
        return self.root_dir.name

    @property
    def project_name(self) -> str:
        """Project name from pyproject.toml ."""
        if self._config_file is not None:
            return str(self._config_file.project_name)
        raise RuntimeError(f"Could not find project name in {self.root_dir}")

    @property
    def version(self) -> str:
        """Get the package version from pyproject.toml or __init__.py.

        Tries pyproject.toml first, falls back to __init__.py if not found.

        Returns:
            str: The package version

        Raises:
            RuntimeError: If version cannot be found in either location
        """
        # TODO: Revisit this logic to ensure it works correctly
        #  with different project structures and edge cases.
        if self._config_file is not None:
            try:
                return self._config_file.project_version
            except RuntimeError:
                for src_root in self._config_file.source_roots:
                    try:
                        return init_version(src_root)
                    except (FileNotFoundError, AttributeError):
                        continue
        raise RuntimeError(f"Could not find package version in {self.root_dir}")

    @version.setter
    def version(self, value: str) -> None:
        """Update the package version in both pyproject.toml and __init__.py.

        Args:
            value: The new version string
        """
        if self._config_file is not None:
            self._config_file.project_version = value
            self._config_file.save()

            for src_root in self._config_file.source_roots:
                try:
                    # TODO: Revisit this logic to ensure it works correctly
                    #  with different project structures and edge cases.
                    init_version(src_root, new_version=value)
                    return
                except (FileExistsError, AttributeError):
                    # Source root doesn't have __init__.py or __version__, skip it
                    pass

        # Add here any additional logic needed to update version
        # in other places if needed (e.g. setup.py, etc.)
        pass

        raise RuntimeError(f"Could not set package version in {self.root_dir}")

    @property
    def authors(self):
        if self._config_file is not None:
            return self._config_file.authors
        raise RuntimeError(f"Could not find authors in {self.root_dir}")

    @property
    def root_dir(self) -> Path | None:
        """Returns the package root directory (where pyproject.toml is) if found, else None."""
        return self._root_dir

    @property
    def source_dirs(self) -> list[Path]:
        """Returns list of source code roots (absolute path)."""
        if self._config_file is not None:
            return self._config_file.source_roots
        raise RuntimeError(f"Could not find source code in {self.root_dir}")

    @property
    def has_config(self) -> bool:
        """Returns True if package has a valid pyproject.toml config file."""
        return self._config_file is not None

    def _resolve_package_name(self) -> str:
        # Try to read from pyproject.toml
        try:
            return self._config_file.project_name
        except RuntimeError as e:
            # print(f"Warning: Could not read package name from pyproject.toml: {e}")
            # Fall back to folder name
            return self.root_dir.name

    def _search_project_file(self):
        # For now, we only support pyproject.toml as the package descriptor.
        # In the future, we could add support for setup.py or setup.cfg if needed here.
        for f in [self._search_pyprojecttoml]:
            try:
                return f()
            except FileNotFoundError:
                continue
        print("Warning: No project file found, package info will be limited.")
        # raise FileNotFoundError(f"No project file found in {self.root_dir}")

    def _search_pyprojecttoml(self) -> PyProjectToml:
        """Search for and open pyproject.toml in the package root directory.

        Returns:
            PyProjectToml: The opened project file

        Raises:
            FileNotFoundError: If pyproject.toml cannot be found
        """
        for p in self.root_dir.glob("pyproject.toml"):
            if p.is_file():
                return PyProjectToml.open(p)
        raise FileNotFoundError(f"pyproject.toml not found in {self.root_dir}")