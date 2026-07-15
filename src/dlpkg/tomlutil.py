from __future__ import annotations

import os
from dataclasses import dataclass, field, fields
from pathlib import Path
from functools import lru_cache
import tomlkit
import logging
from .versioning import SemVer

from typing import Any, ClassVar, List

logger = logging.getLogger(__name__)


@dataclass()
class TomlFile:
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
    # @lru_cache
    def open(cls, file_path: Path | str) -> TomlFile:
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

    @classmethod
    def open_or_create(cls, file_path: Path | str) -> TomlFile:
        """Opens a TOML document from file if it exists; otherwise returns a new instance
        with an empty document and `_doc_path` set to file_path, so a later `.save()` call
        writes to that path.
        """
        instance = cls()
        if isinstance(file_path, str):
            file_path = Path(file_path).resolve()
        try:
            instance.load(file_path)
        except FileNotFoundError:
            instance._doc_path = file_path
        return instance

    def save(self):
        """Writes the current toml document to the original path used for parsing (doc_path).

        Raises:
            ValueError: If doc_path is not set.
        """
        self.save_as(self._doc_path)

    def save_as(self, file_path: Path | str) -> None:
        """Writes the current toml document to file, creating parent directories if needed.
        """
        if isinstance(file_path, str):
            file_path = Path(file_path).resolve()
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(tomlkit.dumps(self._doc), encoding="utf-8")


@dataclass()
class ConfigToml(TomlFile):
    """Utility for reading/writing dlpkg's own config.toml (repo-root-level default settings,
    e.g. the default folder `dlpkg list` scans for published packages).
    """

    DEFAULT_PATH: ClassVar[Path] = Path(__file__).resolve().parent.parent.parent / "config.toml"

    # Keys under [defaults] that hold a filesystem path and therefore need
    # _resolve_relative() treatment on read and Path(...).resolve() normalization on write.
    _PATH_KEYS: ClassVar[frozenset[str]] = frozenset({"build_dir", "publish_dir"})

    @classmethod
    def open_default(cls) -> "ConfigToml":
        """Opens (or, if missing, starts an empty in-memory) config.toml at the fixed
        default location (repo root)."""
        return cls.open_or_create(cls.DEFAULT_PATH)

    def _resolve_relative(self, raw: str) -> Path:
        """Resolves a path from config.toml relative to the config file's own directory
        (not the process's current working directory), consistent with how PyProjectToml
        resolves source_roots relative to the pyproject.toml directory."""
        base = self._doc_path.parent if self._doc_path else Path(".")
        return (base / raw).resolve()

    def get_value(self, key: str, default: Any = None) -> Any:
        """Generic getter for [defaults].<key>. Path keys (_PATH_KEYS) are resolved via
        _resolve_relative(); other keys are returned as their raw parsed TOML value.
        Returns `default` if the [defaults] table or key is missing, or if resolution fails."""
        try:
            raw = self._doc["defaults"][key]
        except Exception:
            return default
        if key in self._PATH_KEYS:
            try:
                return self._resolve_relative(str(raw))
            except Exception:
                return default
        return raw

    def set_value(self, key: str, value: Any) -> None:
        """Generic setter for [defaults].<key>, creating the [defaults] table if needed.
        Path keys are normalized to an absolute path string. Numeric-looking strings (e.g.
        CLI-supplied "10") are coerced to int; other values are stored as-is."""
        if "defaults" not in self._doc:
            self._doc["defaults"] = tomlkit.table()
        if key in self._PATH_KEYS:
            self._doc["defaults"][key] = str(Path(value).resolve())
            return
        if isinstance(value, str):
            try:
                value = int(value)
            except ValueError:
                pass
        self._doc["defaults"][key] = value

    def all_values(self) -> dict[str, Any]:
        """Returns every currently-set [defaults] key, resolved the same way get_value()
        would resolve it. Empty dict if [defaults] is missing/empty."""
        defaults = self._doc.get("defaults", {})
        return {key: self.get_value(key) for key in defaults.keys()}

    @property
    def build_dir(self) -> Path | None:
        """Reads [defaults].build_dir from config.toml. Returns None if unset/unreadable."""
        return self.get_value("build_dir")

    @property
    def publish_dir(self) -> Path | None:
        """Reads [defaults].publish_dir from config.toml. Returns None if unset/unreadable."""
        return self.get_value("publish_dir")

    @publish_dir.setter
    def publish_dir(self, value: Path | str) -> None:
        """Writes [defaults].publish_dir into config.toml, creating the [defaults] table if needed."""
        self.set_value("publish_dir", value)


@dataclass()
class PyProjectToml(TomlFile):
    """Utility for reading/writing pyproject.toml"""

    @property
    def project_name(self) -> str:
        """Reads [project].name from pyproject.toml"""
        try:
            return str(self._doc["project"]["name"])
        except Exception as e:
            raise RuntimeError(f"Could not read project name from {self._doc_path.name}") from e

    @property
    def project_version(self) -> str:
        """Reads/Writes [project].version in pyproject.toml"""
        try:
            return str(self._doc["project"]["version"])
        except Exception as e:
            raise RuntimeError(f"Could not read project version from {self._doc_path.name}") from e

    @project_version.setter
    def project_version(self, version: str) -> None:
        """Writes [project].version in pyproject.toml
        Validates that version is in "*x.y.z*" format.
        """
        # Validate version format
        ver = SemVer.parse(version)
        # Set version
        # if "project" not in self._doc or "version" not in self._doc["project"]:
        #     raise RuntimeError("Missing [project].version in pyproject.toml")
        try:
            self._doc["project"]["version"] = str(ver)
        except:
            raise RuntimeError("Missing [project].version in pyproject.toml")

        # TODO: Should it be responsible for creating the [project].version item if it doesn't exist?
        # except Exception as e:
        #     table = tomlkit.table()
        #     table.add("version", str(ver))
        #     self._doc.add("project", table)

    @property
    def authors(self) -> List[str]:
        """Reads [project].authors from pyproject.toml and returns the authors name if available."""
        authors_out = []
        try:
            authors = self._doc["project"]["authors"]
            if isinstance(authors, list) and len(authors) > 0:
                for a in authors:
                    if isinstance(a, dict) and "name" in a:
                        authors_out.append(str(a["name"]))
                    elif isinstance(a, str):
                        authors_out.append(a)
        except Exception as e:
            raise RuntimeError(f"Could not read project authors from {self._doc_path.name}") from e
        return authors_out

    @property
    def source_roots(self) -> List[Path]:
        """Returns list of source code roots (absolute path).

        Robustly derives source roots from setuptools config.
        It falls back to reasonable defaults if config is missing or incomplete:
        - If [tool.setuptools.packages.find].where is specified, use those paths.
        - Else if [tool.setuptools.package-dir] has a "" key, use that as the base path.
        - Else if "src" or "python" directories exist in the repo root, use those.

        # TODO: We could also consider supporting other common patterns, e.g. "lib",
                or looking for any directories containing __init__.py files.
        # TODO: We could also consider supporting non-setuptools configs in the future,
                e.g. flit or poetry, but for now we will just focus on setuptools since it's the most common and flexible.
        # TODO: We could also consider adding some caching here since this can be
                a bit expensive to compute, but for now we will just compute it
                on the fly since it's not too bad and we want to ensure it reflects any changes to the config.
        """
        tool = self._doc.get("tool", {})
        st = tool.get("setuptools", {})

        package_dir = st.get("package-dir", {}) or {}
        base = package_dir.get("", "").strip()  # e.g. "src" or "python"

        find = st.get("packages", {}).get("find", {})
        where = list(find.get("where", []))

        roots: list[Path] = []

        # PyProjectToml must be located at repo root, so we can resolve relative paths from there.
        repo_root = self._doc_path.parent

        # Resolve roots relative to repo root
        for w in where:
            wr = (repo_root / w).resolve()
            if wr not in roots:
                roots.append(wr)

        logger.debug("Resolved source roots from [tool.setuptools.packages.find].where: %s", roots)

        # If `where` missing, fall back to package-dir base (or repo root)
        if not roots:
            b = (repo_root / base).resolve() if base else repo_root.resolve()
            if b not in roots:
                roots.append(b)

        logger.debug("Resolved source roots after considering [tool.setuptools.package-dir]: %s", roots)

        # Fall back to default "src" if it exists
        # TODO: This should be handled by the caller since this is not the part of the config.
        if not roots:
            for default_src in ['src', 'python']:
                candidate = (repo_root / default_src).resolve()
                if default_src not in roots:
                    roots.append(candidate)

        logger.debug("Resolved source roots after considering default src dirs: %s", roots)

        # Filter out non-existing roots and add any subdirectories (e.g. for namespace packages)
        out_dir = []
        for root in roots:
            if root.is_dir() and root not in out_dir:
                out_dir.append(root)

        logger.debug("Final resolved source roots after filtering non-existing and adding subdirectories: %s", out_dir)

        # TODO: Should we fail here or just return empty list and let caller handle it?
        if not out_dir:
            raise RuntimeError("No source roots found!")

        return out_dir
