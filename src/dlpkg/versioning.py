"""
Versioning utilities: SemVer parsing, comparison and bumping, plus reading and writing
`__version__` in a package's `__init__.py`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import total_ordering
from pathlib import Path

_VERSION_RE = re.compile(r'__version__(?:\s*:\s*[\w\[\].]+)?\s*=\s*([\'"])([^\'"]+)\1')

_SEMVER_RE = re.compile(
    r"""
    (?P<major>0|[1-9]\d*)\.
    (?P<minor>0|[1-9]\d*)\.
    (?P<patch>0|[1-9]\d*)
    (?:-(?P<prerelease>[0-9A-Za-z.-]+))?
    (?:\+(?P<build>[0-9A-Za-z.-]+))?
    """,
    re.VERBOSE,
)

DEFAULT_PRERELEASE_LABEL = "alpha"


def _find_init_version(source_root: Path) -> tuple[Path, str, re.Match]:
    """Returns (path, text, match) for the first `__init__.py` under source_root that assigns
    `__version__`.

    Raises:
        FileNotFoundError: if no `__init__.py` files exist under source_root
        AttributeError: if none of them assigns `__version__`
    """
    paths = sorted(source_root.glob("**/__init__.py"))
    if not paths:
        raise FileNotFoundError(f"No __init__.py files found in {source_root}!")
    for init_path in paths:
        text = init_path.read_text(encoding="utf-8")
        m = _VERSION_RE.search(text)
        if m:
            return init_path, text, m
    raise AttributeError(f"__version__ not found in any __init__.py files in {source_root}!")


def read_init_version(source_root: Path) -> str:
    """Returns the `__version__` string from the first matching `__init__.py` under source_root."""
    return _find_init_version(source_root)[2].group(2)


def write_init_version(source_root: Path, version: str) -> None:
    """Replaces the `__version__` assignment in the first matching `__init__.py` under source_root."""
    init_path, text, m = _find_init_version(source_root)
    quote = m.group(1)
    new_text = text[:m.start()] + f"__version__ = {quote}{version}{quote}" + text[m.end():]
    init_path.write_text(new_text, encoding="utf-8")


@total_ordering
@dataclass(frozen=True)
class SemVer:
    major: int
    minor: int
    patch: int
    prerelease: str | None = None
    build: str | None = None

    @classmethod
    def parse(cls, s: str) -> SemVer:
        m = _SEMVER_RE.search(s)
        if not m:
            raise ValueError(f"Invalid semantic version: {s!r}")
        return cls(
            major=int(m.group("major")),
            minor=int(m.group("minor")),
            patch=int(m.group("patch")),
            prerelease=m.group("prerelease"),
            build=m.group("build"),
        )

    @property
    def core(self) -> tuple[int, int, int]:
        """Returns (major, minor, patch) tuple for core version comparison."""
        return (self.major, self.minor, self.patch)

    @property
    def is_prerelease(self) -> bool:
        """Returns True if this version has a prerelease component."""
        return self.prerelease is not None

    def bump(self, part: str) -> SemVer:
        """Bumps major/minor/patch (resetting lower parts and clearing prerelease/build),
        or the prerelease numeric suffix."""
        if part == "major":
            return SemVer(self.major + 1, 0, 0)
        if part == "minor":
            return SemVer(self.major, self.minor + 1, 0)
        if part == "patch":
            return SemVer(self.major, self.minor, self.patch + 1)
        if part == "prerelease":
            return self.bump_prerelease()
        raise ValueError(f"Unknown version part: {part}")

    def bump_prerelease(self, label: str | None = None) -> SemVer:
        """
        Bump prerelease numeric suffix:
          - 1.2.3-alpha.1 -> 1.2.3-alpha.2
          - 1.2.3-alpha   -> 1.2.3-alpha.1
          - 1.2.3         -> 1.2.3-<label>.1  (label defaults to DEFAULT_PRERELEASE_LABEL)
          - 1.2.3-rc.9+build -> 1.2.3-rc.10+build (keeps build metadata)
        `label` is only used when there is no existing prerelease.
        """
        if self.prerelease is None:
            lab = label or DEFAULT_PRERELEASE_LABEL
            return SemVer(self.major, self.minor, self.patch, f"{lab}.1", self.build)

        parts = self.prerelease.split(".")
        if parts[-1].isdigit():
            parts[-1] = str(int(parts[-1]) + 1)
        else:
            parts.append("1")
        return SemVer(self.major, self.minor, self.patch, ".".join(parts), self.build)

    def __eq__(self, other: object) -> bool:
        """Equality ignores build metadata, consistent with SemVer precedence rules."""
        if not isinstance(other, SemVer):
            return NotImplemented
        return (self.core, self.prerelease) == (other.core, other.prerelease)

    def __hash__(self) -> int:
        return hash((self.core, self.prerelease))

    def __lt__(self, other: object) -> bool:
        """Implements SemVer precedence rules for ordering."""
        if not isinstance(other, SemVer):
            return NotImplemented
        if self.core != other.core:
            return self.core < other.core
        return self._cmp_prerelease(self.prerelease, other.prerelease) < 0

    def __str__(self) -> str:
        v = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            v += f"-{self.prerelease}"
        if self.build:
            v += f"+{self.build}"
        return v

    @classmethod
    def _cmp_prerelease(cls, a: str | None, b: str | None) -> int:
        """
        SemVer precedence rules:
        - No prerelease > prerelease (i.e. 1.0.0 > 1.0.0-alpha)
        - Compare dot-separated identifiers left-to-right
        - Numeric identifiers compare numerically
        - Numeric < non-numeric
        - If all equal but one has extra identifiers, longer one is greater
        """
        if a is None and b is None:
            return 0
        if a is None:
            return 1
        if b is None:
            return -1

        aa = cls._split_prerelease(a)
        bb = cls._split_prerelease(b)

        for x, y in zip(aa, bb):
            if x == y:
                continue
            x_is_int = isinstance(x, int)
            y_is_int = isinstance(y, int)
            if x_is_int and y_is_int:
                return -1 if x < y else 1
            if x_is_int:
                return -1
            if y_is_int:
                return 1
            return -1 if str(x) < str(y) else 1

        if len(aa) == len(bb):
            return 0
        return -1 if len(aa) < len(bb) else 1

    @staticmethod
    def _split_prerelease(pr: str) -> list[int | str]:
        """"alpha.1" -> ["alpha", 1]"""
        return [int(token) if token.isdigit() else token for token in pr.split(".")]
