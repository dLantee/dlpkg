import zipfile
from pathlib import Path

import pytest

from dlpkg.builder import WORK_DIR, BuildError, build_package


def test_build_package_sdist_adds_tarball(temp_toml_package: Path):
    artifacts = build_package(temp_toml_package, temp_toml_package / "dist", sdist=True)
    assert sorted(a.suffix for a in artifacts) == [".gz", ".whl"]


def test_build_package_ignores_stale_workspace(temp_toml_package: Path):
    stale = temp_toml_package / WORK_DIR / "lib" / "my_package" / "deleted.py"
    stale.parent.mkdir(parents=True)
    stale.write_text("", encoding="utf-8")
    [wheel] = build_package(temp_toml_package, temp_toml_package / "dist")
    assert "my_package/deleted.py" not in zipfile.ZipFile(wheel).namelist()


def test_build_package_rebuild_replaces_wheel_and_keeps_others(temp_toml_package: Path):
    dist = temp_toml_package / "dist"
    dist.mkdir()
    older = dist / "my_project_name-1.0.0-py3-none-any.whl"
    older.write_text("old", encoding="utf-8")
    [first] = build_package(temp_toml_package, dist)
    [second] = build_package(temp_toml_package, dist)
    assert first == second
    assert sorted(dist.iterdir()) == sorted([older, second])


def test_build_package_rejects_out_dir_inside_workspace(temp_toml_package: Path):
    with pytest.raises(BuildError, match="emptied"):
        build_package(temp_toml_package, temp_toml_package / WORK_DIR / "out")
