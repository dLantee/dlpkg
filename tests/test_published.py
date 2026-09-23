from datetime import datetime
from pathlib import Path

import pytest
import tomlkit

from dlpkg.published import (METADATA_FILE, PublishedVersion, find_published, parse_version_label,
                             scan_published, with_build_tag, write_metadata)
from dlpkg.versioning import SemVer


def test_write_metadata_then_read_back(tmp_path: Path):
    folder = tmp_path / "pkg" / "rel-1.2.5"
    folder.mkdir(parents=True)
    write_metadata(folder, "pkg", "rel", "1.2.5", "abc1234")
    assert (folder / METADATA_FILE).is_file()

    published = PublishedVersion.from_folder(folder)
    assert published.channel == "rel"
    assert published.version == SemVer(1, 2, 5)
    assert published.commit == "abc1234"
    assert published.label == "rel-1.2.5"
    assert abs((datetime.now() - published.published_at).total_seconds()) < 60


def test_folder_without_metadata_falls_back_to_ctime(tmp_path: Path):
    folder = tmp_path / "pkg" / "dev-1.0.0-alpha.1"
    folder.mkdir(parents=True)
    published = PublishedVersion.from_folder(folder)
    assert published.commit is None
    assert published.published_at == datetime.fromtimestamp(folder.stat().st_ctime)


def test_from_folder_rejects_bad_names(tmp_path: Path):
    for name in ["not-a-valid-format-here", "rel-not-semver", "plain"]:
        folder = tmp_path / name
        folder.mkdir()
        assert PublishedVersion.from_folder(folder) is None


def test_with_build_tag():
    assert with_build_tag("1.2.5", "abc1234") == "1.2.5+abc1234"
    assert with_build_tag("1.2.5-alpha.1", "abc1234") == "1.2.5-alpha.1+abc1234"
    assert with_build_tag("1.2.5+already", "abc1234") == "1.2.5+already"
    assert with_build_tag("1.2.5", None) == "1.2.5"


def test_parse_version_label():
    assert parse_version_label("rel-1.2.3+abc") == ("rel", SemVer(1, 2, 3, build="abc"))
    with pytest.raises(ValueError, match="channel"):
        parse_version_label("foo-1.0.0")
    with pytest.raises(ValueError):
        parse_version_label("rel-x")


def test_scan_published_sorts_newest_first_and_limits(published_versions_dir: Path):
    found = scan_published(published_versions_dir, "my_package")
    assert [p.label for p in found["rel"]] == ["rel-2.0.0", "rel-1.10.0", "rel-1.9.0", "rel-1.2.5", "rel-1.0.0"]
    assert [p.label for p in found["dev"]] == ["dev-2.0.0-beta.1", "dev-1.2.3-alpha.1"]

    limited = scan_published(published_versions_dir, "my_package", limit=2)
    assert [p.label for p in limited["rel"]] == ["rel-2.0.0", "rel-1.10.0"]


def test_scan_published_uses_metadata_timestamp(published_versions_dir: Path):
    folder = published_versions_dir / "my_package" / "rel-1.0.0"
    stamp = datetime(2020, 1, 2, 3, 4, 5)
    doc = tomlkit.document()
    doc["publish"] = {"name": "my_package", "channel": "rel", "version": "1.0.0", "published_at": stamp}
    (folder / METADATA_FILE).write_text(tomlkit.dumps(doc), encoding="utf-8")

    found = scan_published(published_versions_dir, "my_package")
    assert next(p for p in found["rel"] if p.label == "rel-1.0.0").published_at == stamp


def test_find_published(published_versions_dir: Path):
    published = find_published(published_versions_dir, "my_package", "rel-1.9.0")
    assert published.path == published_versions_dir / "my_package" / "rel-1.9.0"
    with pytest.raises(FileNotFoundError):
        find_published(published_versions_dir, "my_package", "rel-9.9.9")
    with pytest.raises(ValueError):
        find_published(published_versions_dir, "my_package", "nope-1.0.0")
