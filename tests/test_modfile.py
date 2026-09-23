import os
from pathlib import Path

from dlpkg import modfile


def test_write_then_read_mod_file(tmp_path: Path):
    install_dir = tmp_path / "publishes" / "pkg" / "rel-1.2.5"
    install_dir.mkdir(parents=True)
    mod_path = modfile.write_mod_file(tmp_path, "pkg", "1.2.5", install_dir)

    assert mod_path == tmp_path / "pkg.mod"
    lines = mod_path.read_text(encoding="utf-8").splitlines()
    assert lines[0] == f"+ pkg 1.2.5 {install_dir.as_posix()}"
    assert lines[1] == "PYTHONPATH +:= ."
    assert modfile.read_mod_target(mod_path) == install_dir


def test_write_mod_file_overwrites(tmp_path: Path):
    modfile.write_mod_file(tmp_path, "pkg", "1.0.0", tmp_path / "rel-1.0.0")
    modfile.write_mod_file(tmp_path, "pkg", "2.0.0", tmp_path / "rel-2.0.0")
    assert modfile.read_mod_target(tmp_path / "pkg.mod") == tmp_path / "rel-2.0.0"


def test_read_mod_target_missing_or_invalid(tmp_path: Path):
    assert modfile.read_mod_target(tmp_path / "nope.mod") is None
    (tmp_path / "bad.mod").write_text("PYTHONPATH +:= .\n", encoding="utf-8")
    assert modfile.read_mod_target(tmp_path / "bad.mod") is None


def test_first_maya_module_dir_skips_missing(monkeypatch, tmp_path: Path):
    existing = tmp_path / "modules"
    existing.mkdir()
    monkeypatch.setenv(modfile.MAYA_MODULE_PATH_ENV,
                       os.pathsep.join([str(tmp_path / "missing"), f'"{existing}"']))
    assert modfile.first_maya_module_dir() == existing


def test_first_maya_module_dir_unset(monkeypatch):
    monkeypatch.delenv(modfile.MAYA_MODULE_PATH_ENV, raising=False)
    assert modfile.first_maya_module_dir() is None
