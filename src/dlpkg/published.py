"""
The published store: <root>/<name>/<channel>-<version>/ folders written by `dlpkg publish`,
each carrying a METADATA_FILE that records when and from which commit it was published.
"""
from __future__ import annotations

import logging
import os
import shutil
import stat
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from dlpkg.tomlutil import PublishToml
from dlpkg.versioning import SemVer

logger = logging.getLogger(__name__)

REL_CHANNEL = "rel"
DEV_CHANNEL = "dev"
# Publish channel -> heading printed by `dlpkg list`. Published folders are named <channel>-<version>.
CHANNELS = {REL_CHANNEL: "Published versions", DEV_CHANNEL: "Development versions"}
METADATA_FILE = "dlpkg.toml"


def version_label(channel: str, version: SemVer | str) -> str:
    """Folder name of a published version: <channel>-<version>."""
    return f"{channel}-{version}"


def with_build_tag(version: str, commit: str | None) -> str:
    """Adds `commit` as SemVer build metadata unless the version already carries some, so dev
    publishes from different commits never land in the same folder."""
    ver = SemVer.parse(version)
    if not commit or ver.build:
        return version
    return str(SemVer(ver.major, ver.minor, ver.patch, ver.prerelease, commit))


def parse_version_label(label: str) -> tuple[str, SemVer]:
    """Splits a <channel>-<version> folder name.

    Raises:
        ValueError: if the channel is unknown or the version is not SemVer.
    """
    channel, _, version_str = label.partition("-")
    if channel not in CHANNELS:
        raise ValueError(f"Unknown channel in {label!r}, expected one of {', '.join(CHANNELS)}")
    return channel, SemVer.parse(version_str)


@dataclass(frozen=True)
class PublishedVersion:
    channel: str
    version: SemVer
    path: Path
    published_at: datetime
    commit: str | None = None

    @property
    def label(self) -> str:
        return version_label(self.channel, self.version)

    @classmethod
    def from_folder(cls, path: Path) -> PublishedVersion | None:
        """Reads a published folder, or returns None when its name is not <channel>-<version>.

        Timestamp and commit come from METADATA_FILE; older folders without one fall back to the
        folder's filesystem creation time."""
        try:
            channel, version = parse_version_label(path.name)
        except ValueError:
            return None
        metadata = PublishToml.open_or_create(path / METADATA_FILE)
        published_at = metadata.published_at or datetime.fromtimestamp(path.stat().st_ctime)
        return cls(channel, version, path, published_at, metadata.commit)


def write_metadata(path: Path, name: str, channel: str, version: SemVer | str,
                   commit: str | None) -> Path:
    """Writes METADATA_FILE into a freshly published folder."""
    metadata = PublishToml.open_or_create(path / METADATA_FILE)
    metadata.set_publish_info(name, channel, str(version), datetime.now(), commit)
    metadata.save()
    return metadata.path


def scan_published(root: Path | str, name: str, limit: int | None = None) -> dict[str, list[PublishedVersion]]:
    """Scans <root>/<name>/<channel>-<version> folders for every channel in CHANNELS.

    Entries with an unknown channel or an unparsable version are skipped. Returns, per channel,
    versions sorted newest-first and truncated to `limit` when given. Every channel is present,
    possibly empty.
    """
    pkg_dir = Path(root) / name
    found: dict[str, list[PublishedVersion]] = {channel: [] for channel in CHANNELS}
    if not pkg_dir.is_dir():
        return found

    for entry in pkg_dir.iterdir():
        if not entry.is_dir():
            continue
        published = PublishedVersion.from_folder(entry)
        if published is not None:
            found[published.channel].append(published)

    for versions in found.values():
        versions.sort(key=lambda p: p.version, reverse=True)
        if limit is not None:
            del versions[limit:]
    return found


def _clear_read_only_and_retry(func, path, exc_info) -> None:
    """shutil.rmtree onexc handler: retries once after dropping a read-only attribute."""
    os.chmod(path, stat.S_IWRITE)
    func(path)


def remove_published(published: PublishedVersion) -> None:
    """Deletes a published version folder, including read-only files."""
    shutil.rmtree(published.path, onexc=_clear_read_only_and_retry)


def find_published(root: Path | str, name: str, label: str) -> PublishedVersion:
    """Returns the published <channel>-<version> folder of `name`.

    Raises:
        ValueError: if `label` is not a valid <channel>-<version>.
        FileNotFoundError: if no such folder was published.
    """
    channel, version = parse_version_label(label)
    path = Path(root) / name / version_label(channel, version)
    published = PublishedVersion.from_folder(path) if path.is_dir() else None
    if published is None:
        raise FileNotFoundError(f"{name} {label} is not published under {Path(root)}")
    return published
