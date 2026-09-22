import pytest

from dlpkg.versioning import SemVer, read_init_version, write_init_version


def test_bump():
    v1 = SemVer.parse("1.2.3")
    assert str(v1) == "1.2.3"
    assert str(v1.bump("patch")) == "1.2.4"
    assert str(v1.bump("minor")) == "1.3.0"
    assert str(v1.bump("major")) == "2.0.0"


def test_bump_prerelease():
    v2 = SemVer.parse("1.2.3-alpha.1+build.456")
    assert str(v2) == "1.2.3-alpha.1+build.456"
    assert str(v2.bump_prerelease()) == "1.2.3-alpha.2+build.456"
    assert str(v2.bump_prerelease("beta")) == "1.2.3-alpha.2+build.456"  # label ignored since prerelease already exists
    v3 = SemVer.parse("1.2.3")
    assert str(v3.bump_prerelease("rc")) == "1.2.3-rc.1"


def test_equal_versions_hash_alike_regardless_of_build():
    a = SemVer.parse("1.2.3-rc.1+build.1")
    b = SemVer.parse("1.2.3-rc.1+build.2")
    assert a == b
    assert hash(a) == hash(b)
    assert len({a, b}) == 1


def test_invalid_version():
    with pytest.raises(ValueError):
        SemVer.parse("invalid")


def test_read_and_write_init_version(temp_toml_package):
    src_path = temp_toml_package / "src" / "my_package"
    assert read_init_version(src_path) == "1.2.5"
    write_init_version(src_path, "1.3.0")
    assert read_init_version(src_path) == "1.3.0"


def test_init_version_errors(tmp_path):
    with pytest.raises(FileNotFoundError):
        read_init_version(tmp_path)
    (tmp_path / "__init__.py").write_text("x = 1", encoding="utf-8")
    with pytest.raises(AttributeError):
        read_init_version(tmp_path)
