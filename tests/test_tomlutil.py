import pytest
from pathlib import Path

from dlpkg.tomlutil import TomlFile, PyProjectToml, ConfigToml
from fixtures import temp_toml_package


def test_tomldata_write_n_read(temp_toml_package):
    toml_file_path = temp_toml_package / "pyproject.toml"
    # Read back the file to verify
    doc = TomlFile.open(toml_file_path)
    assert doc['project']['name'] == "my_project_name"
    assert doc['project']['version'] == "1.2.5"
    assert doc['project']['authors'] == [{'name': 'John Doe', 'email': 'asd@qwe.com'}]

def test_read_data_from_pyproject(temp_toml_package):
    toml_file_path = temp_toml_package / "pyproject.toml"
    # Read back the file to verify
    doc = PyProjectToml.open(toml_file_path)
    assert doc.project_name == "my_project_name"
    assert doc.project_version == "1.2.5"
    assert doc.authors == ["John Doe"]
    assert doc.source_roots == [temp_toml_package / "my_package" / "src"]

    doc.project_version = "1.3.0"
    assert doc.project_version == "1.3.0"


def test_config_open_or_create_missing_file(tmp_path):
    cfg = ConfigToml.open_or_create(tmp_path / "config.toml")
    assert cfg.install_dir is None
    assert cfg.build_dir is None
    assert cfg._doc_path == (tmp_path / "config.toml").resolve()


def test_config_reads_renamed_keys(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text('[defaults]\ninstall_dir = "D:/Extensions/maya/modules"\nbuild_dir = "./build"\n', encoding="utf-8")
    cfg = ConfigToml.open(path)
    assert cfg.install_dir == Path("D:/Extensions/maya/modules").resolve()
    assert cfg.build_dir == (tmp_path / "build").resolve()


def test_config_install_dir_roundtrip(tmp_path):
    path = tmp_path / "config.toml"
    cfg = ConfigToml.open_or_create(path)
    cfg.install_dir = tmp_path / "publishes"
    cfg.save()

    reopened = ConfigToml.open(path)
    assert reopened.install_dir == (tmp_path / "publishes").resolve()


if __name__ == "__main__":
    pytest.main([__file__])