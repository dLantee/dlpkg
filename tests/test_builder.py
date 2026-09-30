import zipfile
from pathlib import Path

import pytest

from dlpkg.builder import WORK_DIR, BuildError, build_leftovers, build_package


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


def _make_leftovers(root: Path) -> dict[str, Path]:
    folders = {"build": root / WORK_DIR, "dist": root / "dist", "egg_info": root / "src" / "my_package.egg-info"}
    for folder in folders.values():
        folder.mkdir(parents=True)
    return folders


def test_build_leftovers_finds_all(temp_toml_package: Path):
    folders = _make_leftovers(temp_toml_package)
    found = build_leftovers(temp_toml_package, folders["dist"], [temp_toml_package / "src"])
    assert found == [folders["build"], folders["dist"], folders["egg_info"]]


@pytest.mark.parametrize("kind", ["build", "dist", "egg_info"])
def test_build_leftovers_filters_by_kind(temp_toml_package: Path, kind: str):
    folders = _make_leftovers(temp_toml_package)
    flags = {name: name == kind for name in folders}
    found = build_leftovers(temp_toml_package, folders["dist"], [temp_toml_package / "src"], **flags)
    assert found == [folders[kind]]


def test_build_leftovers_skips_missing(temp_toml_package: Path):
    assert build_leftovers(temp_toml_package, temp_toml_package / "dist", [temp_toml_package / "src"]) == []


@pytest.mark.parametrize("outside", [True, False])
def test_build_leftovers_refuses_dist_outside_root(tmp_path: Path, temp_toml_package: Path, outside: bool):
    out_dir = tmp_path / "shared_dist" if outside else temp_toml_package
    out_dir.mkdir(exist_ok=True)
    with pytest.raises(BuildError, match="left alone"):
        build_leftovers(temp_toml_package, out_dir, [])
