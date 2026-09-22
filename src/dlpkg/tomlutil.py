"""
tomlkit wrappers: a generic TomlFile plus typed views over pyproject.toml and dlpkg's config.toml.
All reads and writes go through tomlkit so formatting and comments survive a round trip.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar, Self

import tomlkit

from dlpkg.versioning import SemVer

logger = logging.getLogger(__name__)

_MISSING = (KeyError, TypeError)


@dataclass()
class TomlFile:
    """Base class for TOML data classes with utility methods for reading/writing."""

    _doc: tomlkit.TOMLDocument = field(default_factory=tomlkit.TOMLDocument)
    # Path the document was loaded from; default target for save().
    _doc_path: Path | None = None

    def __getitem__(self, key: str) -> Any:
        return self._doc[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self._doc[key] = value

    @classmethod
    def open(cls, file_path: Path | str) -> Self:
        """Opens a TOML document from file and returns an instance of the class."""
        instance = cls()
        instance.load(file_path)
        return instance

    @classmethod
    def open_or_create(cls, file_path: Path | str) -> Self:
        """Opens a TOML document from file if it exists; otherwise returns an instance with an
        empty document whose `_doc_path` is file_path, so a later `.save()` writes there."""
        instance = cls()
        file_path = Path(file_path).resolve()
        try:
            instance.load(file_path)
        except FileNotFoundError:
            instance._doc_path = file_path
        return instance

    def load(self, file_path: Path | str | None = None) -> None:
        """Reads a toml document from file, or from `_doc_path` when file_path is None.

        Raises:
            ValueError: If file_path is None and `_doc_path` is not set.
            FileNotFoundError: If the file does not exist.
        """
        if file_path is None:
            if self._doc_path is None:
                raise ValueError("file_path is required for reading if doc_path is not set")
            file_path = self._doc_path
        file_path = Path(file_path).resolve()
        if not file_path.is_file():
            raise FileNotFoundError(f"File not found: {file_path}")
        self._doc = tomlkit.parse(file_path.read_text(encoding="utf-8"))
        self._doc_path = file_path

    def save(self) -> None:
        """Writes the document back to `_doc_path`.

        Raises:
            ValueError: If `_doc_path` is not set.
        """
        if self._doc_path is None:
            raise ValueError("doc_path is not set; use save_as(file_path)")
        self.save_as(self._doc_path)

    def save_as(self, file_path: Path | str) -> None:
        """Writes the document to file, creating parent directories if needed."""
        file_path = Path(file_path).resolve()
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(tomlkit.dumps(self._doc), encoding="utf-8")


@dataclass()
class ConfigToml(TomlFile):
    """dlpkg's own config.toml: repo-root-level default settings under a [defaults] table."""

    DEFAULT_PATH: ClassVar[Path] = Path(__file__).resolve().parent.parent.parent / "config.toml"
    DEFAULTS_TABLE: ClassVar[str] = "defaults"

    # Keys under [defaults] that hold a filesystem path: resolved relative to the config file on
    # read, normalised to an absolute path string on write.
    _PATH_KEYS: ClassVar[frozenset[str]] = frozenset({"build_dir", "publish_dir"})

    @classmethod
    def open_default(cls) -> Self:
        """Opens config.toml at DEFAULT_PATH, or an empty in-memory one if it is missing."""
        return cls.open_or_create(cls.DEFAULT_PATH)

    def _resolve_relative(self, raw: str) -> Path:
        """Resolves a path relative to the config file's own directory, not the process cwd."""
        base = self._doc_path.parent if self._doc_path else Path(".")
        return (base / raw).resolve()

    def get_value(self, key: str, default: Any = None) -> Any:
        """Returns [defaults].<key>, path keys resolved to absolute Paths, or `default` when the
        table or key is missing."""
        try:
            raw = self._doc[self.DEFAULTS_TABLE][key]
        except _MISSING:
            return default
        if key in self._PATH_KEYS:
            return self._resolve_relative(str(raw))
        return raw

    def set_value(self, key: str, value: Any) -> None:
        """Sets [defaults].<key>, creating the table if needed. Path keys are stored as absolute
        path strings; numeric-looking strings (e.g. CLI-supplied "10") are stored as int."""
        if self.DEFAULTS_TABLE not in self._doc:
            self._doc[self.DEFAULTS_TABLE] = tomlkit.table()
        if key in self._PATH_KEYS:
            value = str(Path(value).resolve())
        elif isinstance(value, str):
            try:
                value = int(value)
            except ValueError:
                pass
        self._doc[self.DEFAULTS_TABLE][key] = value

    def all_values(self) -> dict[str, Any]:
        """Returns every set [defaults] key, resolved like get_value(). Empty if none."""
        defaults = self._doc.get(self.DEFAULTS_TABLE, {})
        return {key: self.get_value(key) for key in defaults}

    @property
    def build_dir(self) -> Path | None:
        return self.get_value("build_dir")

    @property
    def publish_dir(self) -> Path | None:
        return self.get_value("publish_dir")

    @publish_dir.setter
    def publish_dir(self, value: Path | str) -> None:
        self.set_value("publish_dir", value)


@dataclass()
class PyProjectToml(TomlFile):
    """Typed accessors over pyproject.toml's [project] and [tool.setuptools] tables."""

    @property
    def project_name(self) -> str:
        try:
            return str(self._doc["project"]["name"])
        except _MISSING as e:
            raise RuntimeError(f"Could not read project name from {self._doc_path}") from e

    @property
    def project_version(self) -> str:
        try:
            return str(self._doc["project"]["version"])
        except _MISSING as e:
            raise RuntimeError(f"Could not read project version from {self._doc_path}") from e

    @project_version.setter
    def project_version(self, version: str) -> None:
        """Writes a validated SemVer string into [project].version."""
        ver = SemVer.parse(version)
        try:
            self._doc["project"]["version"] = str(ver)
        except _MISSING as e:
            raise RuntimeError(f"Missing [project] table in {self._doc_path}") from e

    @property
    def authors(self) -> list[str]:
        """Author names from [project].authors; entries may be tables with a name or plain strings."""
        try:
            authors = self._doc["project"]["authors"]
        except _MISSING as e:
            raise RuntimeError(f"Could not read project authors from {self._doc_path}") from e
        names = []
        for a in authors:
            if isinstance(a, dict) and "name" in a:
                names.append(str(a["name"]))
            elif isinstance(a, str):
                names.append(a)
        return names

    @property
    def source_roots(self) -> list[Path]:
        """Source roots (absolute, existing) derived the way setuptools does:
        [tool.setuptools.packages.find].where if set, else [tool.setuptools.package-dir]'s ""
        entry, else the pyproject.toml directory itself.

        Raises:
            RuntimeError: if none of the candidates exist on disk.
        """
        setuptools = self._doc.get("tool", {}).get("setuptools", {})
        repo_root = self._doc_path.parent

        where = list(setuptools.get("packages", {}).get("find", {}).get("where", []))
        if not where:
            where = [(setuptools.get("package-dir", {}) or {}).get("", "").strip()]

        roots: list[Path] = []
        for w in where:
            candidate = (repo_root / w).resolve()
            if candidate.is_dir() and candidate not in roots:
                roots.append(candidate)
        logger.debug("Resolved source roots: %s", roots)

        if not roots:
            raise RuntimeError(f"No source roots found for {self._doc_path}")
        return roots
