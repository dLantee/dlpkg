from __future__ import annotations

from dlpkg.package import PythonPackage
from fixtures import temp_toml_package


def test_package_info_toml(temp_toml_package):
    pkg_info = PythonPackage(temp_toml_package)
    assert pkg_info.name == "test_package"
    assert pkg_info.project_name == "my_project_name"
    assert pkg_info.version == "1.2.5"
    assert pkg_info.root_dir == temp_toml_package
    assert pkg_info.source_dirs == [temp_toml_package / "src"]


if __name__ == "__main__":
    import pytest
    pytest.main([__file__])

