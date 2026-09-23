"""
Keep-a-Changelog editing: turns the `## [Unreleased]` section into a dated release heading and
repoints the compare links at the foot of the file.
"""
from __future__ import annotations

import re
from datetime import date

CHANGELOG_FILE = "CHANGELOG.md"
UNRELEASED_HEADING = "## [Unreleased]"
_SECTION_START = ("## [", "[Unreleased]:")
_UNRELEASED_LINK_RE = re.compile(
    r"^\[Unreleased\]:\s*(?P<base>\S+)/compare/(?P<previous>\S+)\.\.\.HEAD[ \t]*$", re.MULTILINE)


def release_changelog(text: str, version: str, release_date: date) -> str:
    """Moves everything under `## [Unreleased]` into a new `## [version] - date` section, leaving
    an empty Unreleased heading above it, and adds the release's compare link when the file has them.

    Raises:
        ValueError: if there is no Unreleased section, or it has no entries.
    """
    lines = text.splitlines(keepends=True)
    try:
        start = next(i for i, line in enumerate(lines) if line.rstrip() == UNRELEASED_HEADING)
    except StopIteration:
        raise ValueError(f"No {UNRELEASED_HEADING!r} section in the changelog") from None
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith(_SECTION_START)), len(lines))

    body = lines[start + 1:end]
    if not "".join(body).strip():
        raise ValueError("The Unreleased section is empty; write the changelog entries first")

    heading = f"## [{version}] - {release_date:%Y-%m-%d}\n"
    text = "".join(lines[:start + 1] + ["\n", heading] + body + lines[end:])

    m = _UNRELEASED_LINK_RE.search(text)
    if m:
        base, previous = m.group("base"), m.group("previous")
        links = f"[Unreleased]: {base}/compare/v{version}...HEAD\n[{version}]: {base}/compare/{previous}...v{version}"
        text = text[:m.start()] + links + text[m.end():]
    return text
