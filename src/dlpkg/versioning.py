"""
Versioning utilities.
"""
from __future__ import annotations

import re
from pathlib import Path
from dataclasses import dataclass
from functools import total_ordering
from typing import Optional, Tuple, List, Union



_VERSION_RE = re.compile(r'__version__(?:\s*:\s*[\w\[\].]+)?\s*=\s*([\'"])([^\'"]+)\1')

def init_version(source_root: Path, new_version: str = "", verbose: bool = False) -> str:
    """If new_version is empty, return the existing version from a matching __init__.py.
    Otherwise, update the first matching __init__.py and return new_version.

    Raises:
        FileNotFoundError: if no __init__.py files exist under source_root
        AttributeError: if no __version__ assignment is found
        ValueError: if existing __version__ can't be parsed when new_version is empty
    """
    paths = sorted(source_root.glob("**/__init__.py"))
    if not paths:
        raise FileNotFoundError(f"No __init__.py files found in {source_root}!")

    # Read-only mode: return first parsed version
    if new_version == "":
        for init_path in paths:
            text = init_path.read_text(encoding="utf-8")
            m = _VERSION_RE.search(text)
            if m:
                return m.group(2)
        raise AttributeError(f"__version__ not found in any __init__.py files in {source_root}!")

    # Update mode: update first file that matches
    for init_path in paths:
        text = init_path.read_text(encoding="utf-8")
        m = _VERSION_RE.search(text)
        if not m:
            continue

        def repl(match: re.Match) -> str:
            quote = match.group(1)
            return f'__version__ = {quote}{new_version}{quote}'

        new_text, n = _VERSION_RE.subn(repl, text, count=1)
        if n:
            init_path.write_text(new_text, encoding="utf-8")
            if verbose:
                print(f"Updated version in {init_path}: {m.group(2)} -> {new_version}")
            return new_version

    raise AttributeError(f"__version__ not found in any __init__.py files in {source_root}!")


@total_ordering
@dataclass(frozen=True)
class SemVer:
    major: int
    minor: int
    patch: int
    prerelease: Optional[str] = None
    build: Optional[str] = None

    SEMVER_RE = re.compile(
        r"""
        (?P<major>0|[1-9]\d*)\.
        (?P<minor>0|[1-9]\d*)\.
        (?P<patch>0|[1-9]\d*)
        (?:-(?P<prerelease>[0-9A-Za-z.-]+))?
        (?:\+(?P<build>[0-9A-Za-z.-]+))?
        """,
        re.VERBOSE,
    )

    @classmethod
    def parse(cls, s: str) -> "SemVer":
        m = cls.SEMVER_RE.search(s)
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
    def core(self) -> Tuple[int, int, int]:
        """Returns (major, minor, patch) tuple for core version comparison."""
        return (self.major, self.minor, self.patch)

    @property
    def is_prerelease(self) -> bool:
        """Returns True if this version has a prerelease component."""
        return self.prerelease is not None

    def bump(self, part: str) -> "SemVer":
        """Bumps major/minor/patch. Resets lower parts and clears prerelease/build."""
        if part == "major":
            return SemVer(self.major + 1, 0, 0)
        if part == "minor":
            return SemVer(self.major, self.minor + 1, 0)
        if part == "patch":
            return SemVer(self.major, self.minor, self.patch + 1)
        if part == "prerelease":
            # TODO: Missing argument; Provide support for bumping prerelease with label (e.g. alpha -> beta, or alpha.1 -> beta.1)
            return self.bump_prerelease()
        raise ValueError(f"Unknown version part: {part}")

    def bump_prerelease(self, label: Optional[str] = None) -> "SemVer":
        """
        Bump prerelease numeric suffix:
          - 1.2.3-alpha.1 -> 1.2.3-alpha.2
          - 1.2.3-alpha   -> 1.2.3-alpha.1
          - 1.2.3         -> 1.2.3-<label>.1  (label required or defaults to 'alpha')
          - 1.2.3-rc.9+build -> 1.2.3-rc.10+build (keeps build metadata)
        If label is provided and current prerelease exists, it is only used when
        there is no existing label (i.e. no prerelease).
        """
        if self.prerelease is None:
            lab = label or "alpha"
            return SemVer(self.major, self.minor, self.patch, f"{lab}.1", self.build)

        parts = self.prerelease.split(".")
        if parts and parts[-1].isdigit():
            parts[-1] = str(int(parts[-1]) + 1)
        else:
            parts.append("1")
        return SemVer(self.major, self.minor, self.patch, ".".join(parts), self.build)

    def __eq__(self, other: object) -> bool:
        """Equality ignores build metadata, consistent with SemVer precedence rules."""
        if not isinstance(other, SemVer):
            return NotImplemented
        # Build metadata does NOT affect precedence/equality in SemVer ordering sense.
        return (self.major, self.minor, self.patch, self.prerelease) == (
            other.major,
            other.minor,
            other.patch,
            other.prerelease,
        )

    def __lt__(self, other: object) -> bool:
        """Implements SemVer precedence rules for ordering."""
        if not isinstance(other, SemVer):
            return NotImplemented

        if self.core != other.core:
            return self.core < other.core

        pr_cmp = self._cmp_prerelease(self.prerelease, other.prerelease)
        return pr_cmp < 0

    def __str__(self) -> str:
        v = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            v += f"-{self.prerelease}"
        if self.build:
            v += f"+{self.build}"
        return v

    @classmethod
    def _cmp_prerelease(cls, a: Optional[str], b: Optional[str]) -> int:
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
            if x_is_int and not y_is_int:
                return -1
            if not x_is_int and y_is_int:
                return 1

            # both strings
            return -1 if str(x) < str(y) else 1

        # all shared identifiers equal; shorter has lower precedence
        if len(aa) == len(bb):
            return 0
        return -1 if len(aa) < len(bb) else 1

    @staticmethod
    def _split_prerelease(pr: str) -> List[Union[int, str]]:
        # "alpha.1" -> ["alpha", 1]
        out: List[Union[int, str]] = []
        for token in pr.split("."):
            if token.isdigit():
                out.append(int(token))
            else:
                out.append(token)
        return out
