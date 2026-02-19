import pytest
from dlpkg.versioning import SemVer
from dlpkg.versioning import init_version
from fixtures import temp_toml_package


def test_bump():
    v1 = SemVer.parse("1.2.3")
    assert str(v1) == "1.2.3"
    assert str(v1.bump("patch")) == "1.2.4"
    assert str(v1.bump("minor")) == "1.3.0"
    assert str(v1.bump("major")) == "2.0.0"


def test_bump_prerelease():
    # More complex versions
    v2 = SemVer.parse("1.2.3-alpha.1+build.456")
    assert str(v2) == "1.2.3-alpha.1+build.456"
    assert str(v2.bump_prerelease()) == "1.2.3-alpha.2+build.456"
    assert str(v2.bump_prerelease("beta")) == "1.2.3-alpha.2+build.456"  # label ignored since prerelease already exists
    v3 = SemVer.parse("1.2.3")
    assert str(v3.bump_prerelease("rc")) == "1.2.3-rc.1"


def test_invalid_version():
    with pytest.raises(ValueError):
        SemVer.parse("invalid")


def test_init_version(temp_toml_package):
    src_path = temp_toml_package / "src" / "my_package"
    assert init_version(src_path) == "1.2.5"
    init_version(src_path, "1.3.0")
    assert init_version(src_path) == "1.3.0"


if __name__ == "__main__":
    pytest.main([__file__])