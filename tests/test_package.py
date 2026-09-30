import pytest

from dlpkg.package import PythonPackage, find_package_root
from dlpkg.tomlutil import PyProjectToml
from dlpkg.versioning import read_init_version


def test_package_info_toml(temp_toml_package):
    pkg_info = PythonPackage(temp_toml_package)
    assert pkg_info.name == "test_package"
    assert pkg_info.project_name == "my_project_name"
    assert pkg_info.version == "1.2.5"
    assert pkg_info.root_dir == temp_toml_package
    assert pkg_info.source_dirs == [temp_toml_package / "src"]


def test_set_version_updates_pyproject_and_init(temp_toml_package):
    PythonPackage(temp_toml_package).version = "2.0.0"
    assert PyProjectToml.open(temp_toml_package / "pyproject.toml").project_version == "2.0.0"
    assert read_init_version(temp_toml_package / "src") == "2.0.0"


def test_set_version_without_init_file_updates_pyproject(temp_toml_package):
    (temp_toml_package / "src" / "my_package" / "__init__.py").unlink()
    PythonPackage(temp_toml_package).version = "2.0.0"
    assert PyProjectToml.open(temp_toml_package / "pyproject.toml").project_version == "2.0.0"


def test_set_version_without_version_in_init_updates_pyproject(temp_toml_package):
    (temp_toml_package / "src" / "my_package" / "__init__.py").write_text("x = 1", encoding="utf-8")
    PythonPackage(temp_toml_package).version = "2.0.0"
    assert PyProjectToml.open(temp_toml_package / "pyproject.toml").project_version == "2.0.0"


def test_package_without_pyproject_raises(tmp_path):
    with pytest.raises(FileNotFoundError, match="pyproject.toml"):
        PythonPackage(tmp_path)


def test_find_package_root_from_root(temp_toml_package):
    assert find_package_root(temp_toml_package) == temp_toml_package


def test_find_package_root_from_subfolder(temp_toml_package):
    assert find_package_root(temp_toml_package / "src" / "my_package") == temp_toml_package


def test_find_package_root_outside_package_raises(tmp_path):
    with pytest.raises(FileNotFoundError, match="any parent folder"):
        find_package_root(tmp_path)


def test_find_package_root_missing_dir_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        find_package_root(tmp_path / "missing")


def test_package_from_subfolder(temp_toml_package):
    pkg_info = PythonPackage(temp_toml_package / "src")
    assert pkg_info.root_dir == temp_toml_package
    assert pkg_info.name == "test_package"
