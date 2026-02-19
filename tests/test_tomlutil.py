import pytest

from dlpkg.tomlutil import TomlFile, PyProjectToml
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


if __name__ == "__main__":
    pytest.main([__file__])