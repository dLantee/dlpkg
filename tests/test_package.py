import pytest

from dlpkg.package import PythonPackage
from dlpkg.tomlutil import PyProjectToml
from dlpkg.versioning import read_init_version


def test_package_info_toml(temp_toml_package):
    pkg_info = PythonPackage(temp_toml_package)
    assert pkg_info.name == "test_package"
    assert pkg_info.project_name == "my_project_name"
    assert pkg_info.version == "1.2.5"
    assert pkg_info.root_dir == temp_toml_package
    assert pkg_info.source_dirs == [temp_toml_package / "src"]
    assert pkg_info.has_config


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


def test_package_without_pyproject(tmp_path):
    pkg_info = PythonPackage(tmp_path)
    assert not pkg_info.has_config
    with pytest.raises(RuntimeError):
        pkg_info.version
    with pytest.raises(RuntimeError):
        pkg_info.version = "1.0.0"
