from __future__ import annotations

import os
from dataclasses import dataclass, field, fields
from pathlib import Path
import tomlkit
from .versioning import SemVer



@dataclass()
class TomlData:
    """Base class for TOML data classes with utility methods for reading/writing.

    """

    _doc: tomlkit.TOMLDocument = field(default_factory=tomlkit.TOMLDocument)
    # Path to the TOML document, set when parsing from file.
    # Used as default path for read/write operations.
    _doc_path: Path | None = None

    def __getitem__(self, key: str) -> tomlkit.TOMLDocument:
        """Allows dict-like access to the TOML document."""
        return self._doc[key]

    def __setitem__(self, key, value):
        """Allows dict-like setting of values in the TOML document."""
        self._doc[key] = value

    @classmethod
    def open(cls, file_path: Path | str) -> TomlData:
        """Opens a TOML document from file and returns an instance of the class."""
        instance = cls()
        instance.load(file_path)
        return instance

    def load(self, file_path: Path | str | None) -> None:
        """Reads a toml document from file.

        Args:
            file_path: Optional path to read toml document from.
                If None, will read from the original path used for doc parsing (doc_path).
        Raises:
            ValueError: If file_path is None and doc_path is not set.
            FileNotFoundError: If the specified file does not exist or is not a file.
        """
        if file_path is None:
            if self._doc_path is None:
                raise ValueError("file_path is required for reading if doc_path is not set")
            file_path = self._doc_path
        if isinstance(file_path, str):
            file_path = Path(file_path).resolve()
        if not file_path.exists() and not file_path.is_file():
            raise FileNotFoundError(f"File not found: {file_path}")
        self._doc = tomlkit.parse(file_path.read_text(encoding="utf-8"))
        self._doc_path = file_path

    def save(self):
        """Writes the current toml document to the original path used for parsing (doc_path).

        Raises:
            ValueError: If doc_path is not set.
        """
        self.save_as(self._doc_path)

    def save_as(self, file_path: Path | str) -> None:
        """Writes the current toml document to file.
        """
        if isinstance(file_path, str):
            file_path = Path(file_path).resolve()
        file_path.write_text(tomlkit.dumps(self._doc), encoding="utf-8")


@dataclass()
class ConfigToml(TomlData):
    """Utility for reading/writing config.toml files"""

    @property
    def dist_dir(self) -> Path:
        """Reads distribution folder from config.toml"""
        try:
            return Path(self._doc["defaults"]["distribution_dir"])
        except Exception as e:
            raise RuntimeError("Could not read dist_folder from config.toml") from e

    @property
    def publish_dir(self) -> Path:
        """Reads publish_folder from config.toml"""
        try:
            return Path(self._doc["defaults"]["publish_dir"])
        except Exception as e:
            print(self._doc)
            raise RuntimeError("Could not read publish_folder from config.toml") from e


@dataclass()
class PyProjectToml(TomlData):
    """Utility for reading/writing pyproject.toml"""

    DEFAULT_SRC_DIRS = ["src", "python"]

    @property
    def project_name(self) -> str:
        """Reads [project].name from pyproject.toml"""
        try:
            return str(self._doc["project"]["name"])
        except Exception as e:
            raise RuntimeError("Could not read [project].name from pyproject.toml") from e

    @property
    def project_version(self) -> str:
        """Reads/Writes [project].version in pyproject.toml"""
        try:
            return str(self._doc["project"]["version"])
        except Exception as e:
            raise RuntimeError("Could not read [project].version from pyproject.toml") from e

    @project_version.setter
    def project_version(self, version: str) -> None:
        """Writes [project].version in pyproject.toml
        Validates that version is in "*x.y.z*" format.
        """
        # Validate version format
        ver = SemVer.parse(version)
        # Set version
        if "project" not in self._doc or "version" not in self._doc["project"]:
            raise RuntimeError("Missing [project].version in pyproject.toml")
        self._doc["project"]["version"] = str(ver)

    def source_roots(self, repo_root: Path) -> list[Path]:
        """Returns list of source code roots (absolute path).

        Robustly derives source roots from setuptools config.
        It falls back to reasonable defaults if config is missing or incomplete:
        - If [tool.setuptools.packages.find].where is specified, use those paths.
        - Else if [tool.setuptools.package-dir] has a "" key, use that as the base path.
        - Else if "src" or "python" directories exist in the repo root, use those.
        """
        tool = self._doc.get("tool", {})
        st = tool.get("setuptools", {})

        package_dir = st.get("package-dir", {}) or {}
        base = package_dir.get("", "").strip()  # e.g. "src" or "python"

        find = st.get("packages", {}).get("find", {})
        where = list(find.get("where", []))

        roots: list[Path] = []

        # Resolve roots relative to repo root
        for w in where:
            wr = (repo_root / w).resolve()
            if wr not in roots:
                roots.append(wr)

        # If `where` missing, fall back to package-dir base (or repo root)
        if not roots:
            b = (repo_root / base).resolve() if base else repo_root.resolve()
            if b not in roots:
                roots.append(b)

        # Fall back to default "src" if it exists
        if not roots:
            for default_src in self.DEFAULT_SRC_DIRS:
                candidate = (repo_root / default_src).resolve()
                if default_src not in roots:
                    roots.append(candidate)

        # Filter out non-existing roots and add any subdirectories (e.g. for namespace packages)
        out_dir = []
        for root in roots:
            for f in root.iterdir():
                if f.is_dir() and f.name not in out_dir:
                    out_dir.append(f)

        if not out_dir:
            raise RuntimeError(
                "No source roots found. Check pyproject.toml: "
                "[tool.setuptools].package-dir and [tool.setuptools.packages.find].where"
            )
        return out_dir
