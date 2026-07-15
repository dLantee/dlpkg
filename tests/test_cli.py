from __future__ import annotations
import pytest
import tomlkit
import argparse
from pathlib import Path
from fixtures import temp_toml_package, published_versions_dir # This import creates a temporary package structure for testing
import dlpkg.cli as cli




def test_cmd_version_query(capsys, temp_toml_package):
    args = argparse.Namespace(root_dir=str(temp_toml_package), bump=None)
    rc = cli.cmd_version(args)
    assert rc == 0
    assert capsys.readouterr().out.strip() == "1.2.5"


def test_cmd_version_bump(capsys, temp_toml_package):

    def _read_doc():
        with open(str(temp_toml_package / "pyproject.toml"), "rb") as f:
            data = tomlkit.load(f)
            return data

    # bump - patch
    args = argparse.Namespace(root_dir=str(temp_toml_package), bump="patch")
    rc = cli.cmd_version(args)
    assert rc == 0
    assert "1.2.5 -> 1.2.6" in capsys.readouterr().out
    doc = _read_doc()
    assert doc["project"]["version"] == "1.2.6"
    # bump - minor
    args = argparse.Namespace(root_dir=str(temp_toml_package), bump="minor")
    rc = cli.cmd_version(args)
    assert rc == 0
    assert "1.2.6 -> 1.3.0" in capsys.readouterr().out
    doc = _read_doc()
    assert doc["project"]["version"] == "1.3.0"
    # bump major
    args = argparse.Namespace(root_dir=str(temp_toml_package), bump="major")
    rc = cli.cmd_version(args)
    assert rc == 0
    assert "1.3.0 -> 2.0.0" in capsys.readouterr().out
    doc = _read_doc()
    assert doc["project"]["version"] == "2.0.0"


def test_cmd_build(tmp_path: Path, temp_toml_package: Path):
    dist_path = tmp_path / "dist"
    args = argparse.Namespace(root_dir=str(temp_toml_package), out_dir=str(dist_path))
    rc = cli.cmd_build(args)
    assert rc == 0
    assert any(dist_path.glob("*.whl"))  # check that wheel file is created


def test_publish_basic(tmp_path, temp_toml_package: Path):
    args = argparse.Namespace(root_dir=str(temp_toml_package), out_dir=str(tmp_path))
    rc = cli.cmd_publish(args)
    assert rc == 0


def test_update_args_from_files_publish_out_dir_uses_config_publish_dir(monkeypatch, tmp_path: Path):
    class FakePyProject:
        project_name = "MyProject"
        project_version = "0.1.0"

        def source_roots(self):
            return [Path("src")]

    class FakeConfig:
        publish_dir = tmp_path / "publishes"

    monkeypatch.setattr(cli, "_get_pyproject_doc", lambda root: FakePyProject())
    monkeypatch.setattr(cli, "_get_config_doc", lambda root: FakeConfig())

    args = argparse.Namespace(cmd="publish", root_dir=str(tmp_path), name=None, source_dir=None, version=None, out_dir=None)
    updated = cli._update_args_from_files(args)

    assert updated.out_dir == str(FakeConfig.publish_dir)


def test_update_args_from_files_publish_out_dir_falls_back_to_maya_module_path(monkeypatch, tmp_path: Path):
    class FakePyProject:
        project_name = "MyProject"
        project_version = "0.1.0"

        def source_roots(self):
            return [Path("src")]

    monkeypatch.setattr(cli, "_get_pyproject_doc", lambda root: FakePyProject())

    def raise_file_not_found(root):
        raise FileNotFoundError

    monkeypatch.setattr(cli, "_get_config_doc", raise_file_not_found)
    monkeypatch.setenv("MAYA_MODULE_PATH", str(tmp_path / "mayaModules") + ";" + str(tmp_path / "other"))

    args = argparse.Namespace(cmd="publish", root_dir=str(tmp_path), name=None, source_dir=None, version=None, out_dir=None)
    updated = cli._update_args_from_files(args)

    # Note: cli splits on whitespace, not os.pathsep
    assert updated.out_dir == str(tmp_path / "mayaModules")


def test_update_args_from_files_publish_out_dir_raises_if_no_config_and_no_env(monkeypatch, tmp_path: Path):
    class FakePyProject:
        project_name = "MyProject"
        project_version = "0.1.0"

        def source_roots(self):
            return [Path("src")]

    monkeypatch.setattr(cli, "_get_pyproject_doc", lambda root: FakePyProject())

    def raise_file_not_found(root):
        raise FileNotFoundError

    monkeypatch.setattr(cli, "_get_config_doc", raise_file_not_found)
    monkeypatch.delenv("MAYA_MODULE_PATH", raising=False)

    args = argparse.Namespace(cmd="publish", root_dir=str(tmp_path), name=None, source_dir=None, version=None, out_dir=None)

    with pytest.raises(RuntimeError, match="MAYA_MODULE_PATH"):
        cli._update_args_from_files(args)

def test_cmd_list_basic(capsys, published_versions_dir):
    args = argparse.Namespace(package_name="my_package", dir=str(published_versions_dir), set_default_dir=None)
    rc = cli.cmd_list(args)
    assert rc == 0
    out = capsys.readouterr().out
    assert "Published versions (latest 10):" in out
    assert "Development versions (latest 10):" in out
    # semver order, not string order (2.0.0 > 1.10.0 > 1.9.0 > 1.2.5 > 1.0.0)
    rel_lines = [line for line in out.splitlines() if line.startswith("    rel-")]
    assert rel_lines == ["    rel-2.0.0", "    rel-1.10.0", "    rel-1.9.0", "    rel-1.2.5", "    rel-1.0.0"]
    assert "    dev-2.0.0-beta.1" in out
    assert "    dev-1.2.3-alpha.1" in out
    assert "not-a-valid-format-here" not in out
    assert "not-semver" not in out


def test_cmd_list_truncates_to_latest_10(tmp_path, capsys):
    pkg_dir = tmp_path / "publishes" / "my_package"
    pkg_dir.mkdir(parents=True)
    for i in range(15):
        (pkg_dir / f"rel-1.{i}.0").mkdir()
    args = argparse.Namespace(package_name="my_package", dir=str(tmp_path / "publishes"), set_default_dir=None)
    rc = cli.cmd_list(args)
    assert rc == 0
    out = capsys.readouterr().out
    rel_lines = [l for l in out.splitlines() if l.startswith("    rel-")]
    assert len(rel_lines) == 10
    assert "rel-1.14.0" in rel_lines[0]
    assert not any("1.4.0" in l for l in rel_lines)  # only top 10 of 15 kept


def test_cmd_list_missing_folder_is_empty(tmp_path, capsys):
    args = argparse.Namespace(package_name="ghost_pkg", dir=str(tmp_path / "does_not_exist"), set_default_dir=None)
    rc = cli.cmd_list(args)
    assert rc == 0
    out = capsys.readouterr().out
    assert not any(l.startswith("    rel-") or l.startswith("    dev-") for l in out.splitlines())


def test_cmd_list_requires_package_name(tmp_path):
    args = argparse.Namespace(package_name=None, dir=str(tmp_path), set_default_dir=None)
    with pytest.raises(RuntimeError, match="package_name"):
        cli.cmd_list(args)


def test_cmd_list_set_default_dir_then_used_by_later_call(tmp_path, monkeypatch, capsys, published_versions_dir):
    monkeypatch.setattr(cli.ConfigToml, "DEFAULT_PATH", tmp_path / "cfg" / "config.toml")
    monkeypatch.delenv("DLPKG_PUBLISH_DIR", raising=False)

    set_args = argparse.Namespace(package_name=None, dir=None, set_default_dir=str(published_versions_dir))
    rc = cli.cmd_list(set_args)
    assert rc == 0
    assert (tmp_path / "cfg" / "config.toml").exists()

    list_args = argparse.Namespace(package_name="my_package", dir=None, set_default_dir=None)
    rc2 = cli.cmd_list(list_args)
    assert rc2 == 0
    assert "rel-2.0.0" in capsys.readouterr().out


def test_cmd_list_dir_flag_overrides_env_and_config(monkeypatch, tmp_path, published_versions_dir):
    monkeypatch.setattr(cli.ConfigToml, "DEFAULT_PATH", tmp_path / "unused_config.toml")
    monkeypatch.setenv("DLPKG_PUBLISH_DIR", str(tmp_path / "env_dir"))
    args = argparse.Namespace(package_name="my_package", dir=str(published_versions_dir), set_default_dir=None)
    assert cli.cmd_list(args) == 0  # doesn't error even though env/config point elsewhere


def test_cmd_list_env_var_used_when_no_dir_flag(monkeypatch, tmp_path, published_versions_dir):
    monkeypatch.setattr(cli.ConfigToml, "DEFAULT_PATH", tmp_path / "unused_config.toml")
    monkeypatch.setenv("DLPKG_PUBLISH_DIR", str(published_versions_dir))
    args = argparse.Namespace(package_name="my_package", dir=None, set_default_dir=None)
    assert cli.cmd_list(args) == 0


def test_cmd_list_raises_if_no_dir_env_or_config(monkeypatch, tmp_path):
    monkeypatch.setattr(cli.ConfigToml, "DEFAULT_PATH", tmp_path / "no_such_config.toml")
    monkeypatch.delenv("DLPKG_PUBLISH_DIR", raising=False)
    args = argparse.Namespace(package_name="my_package", dir=None, set_default_dir=None)
    with pytest.raises(RuntimeError, match="DLPKG_PUBLISH_DIR"):
        cli.cmd_list(args)


if __name__ == "__main__":
    pytest.main([__file__])