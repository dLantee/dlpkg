from __future__ import annotations
import pytest
import tomlkit
import argparse
from pathlib import Path
from fixtures import temp_toml_package # This import creates a temporary package structure for testing
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


def test_install_basic(tmp_path, temp_toml_package: Path):
    args = argparse.Namespace(root_dir=str(temp_toml_package), out_dir=str(tmp_path))
    rc = cli.cmd_install(args)
    assert rc == 0


def test_update_args_from_files_install_out_dir_uses_config_publish_dir(monkeypatch, tmp_path: Path):
    class FakePyProject:
        project_name = "MyProject"
        project_version = "0.1.0"

        def source_roots(self):
            return [Path("src")]

    class FakeConfig:
        publish_dir = tmp_path / "publishes"

    monkeypatch.setattr(cli, "_get_pyproject_doc", lambda root: FakePyProject())
    monkeypatch.setattr(cli, "_get_config_doc", lambda root: FakeConfig())

    args = argparse.Namespace(cmd="install", root_dir=str(tmp_path), name=None, source_dir=None, version=None, out_dir=None)
    updated = cli._update_args_from_files(args)

    assert updated.out_dir == str(FakeConfig.publish_dir)


def test_update_args_from_files_install_out_dir_falls_back_to_maya_module_path(monkeypatch, tmp_path: Path):
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

    args = argparse.Namespace(cmd="install", root_dir=str(tmp_path), name=None, source_dir=None, version=None, out_dir=None)
    updated = cli._update_args_from_files(args)

    # Note: cli splits on whitespace, not os.pathsep
    assert updated.out_dir == str(tmp_path / "mayaModules")


def test_update_args_from_files_install_out_dir_raises_if_no_config_and_no_env(monkeypatch, tmp_path: Path):
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

    args = argparse.Namespace(cmd="install", root_dir=str(tmp_path), name=None, source_dir=None, version=None, out_dir=None)

    with pytest.raises(RuntimeError, match="MAYA_MODULE_PATH"):
        cli._update_args_from_files(args)

if __name__ == "__main__":
    pytest.main([__file__])