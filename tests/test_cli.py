import argparse
import re
from pathlib import Path

import pytest
import tomlkit

import dlpkg.cli as cli
from dlpkg.versioning import read_init_version


def test_cmd_version_query(capsys, temp_toml_package):
    args = argparse.Namespace(root_dir=str(temp_toml_package), bump=None)
    rc = cli.cmd_version(args)
    assert rc == 0
    assert capsys.readouterr().out.strip() == "1.2.5"


def test_cmd_version_bump(capsys, temp_toml_package):

    def _read_doc():
        with open(str(temp_toml_package / "pyproject.toml"), "rb") as f:
            return tomlkit.load(f)

    args = argparse.Namespace(root_dir=str(temp_toml_package), bump="patch")
    rc = cli.cmd_version(args)
    assert rc == 0
    assert "1.2.5 -> 1.2.6" in capsys.readouterr().out
    assert _read_doc()["project"]["version"] == "1.2.6"

    args = argparse.Namespace(root_dir=str(temp_toml_package), bump="minor")
    rc = cli.cmd_version(args)
    assert rc == 0
    assert "1.2.6 -> 1.3.0" in capsys.readouterr().out
    assert _read_doc()["project"]["version"] == "1.3.0"

    args = argparse.Namespace(root_dir=str(temp_toml_package), bump="major")
    rc = cli.cmd_version(args)
    assert rc == 0
    assert "1.3.0 -> 2.0.0" in capsys.readouterr().out
    assert _read_doc()["project"]["version"] == "2.0.0"


CHANGELOG_WITH_ENTRIES = """# Changelog

## [Unreleased]

### Added
- New thing.

## [1.2.5] - 2026-01-01

- Old thing.


[Unreleased]: https://example.com/repo/compare/v1.2.5...HEAD
[1.2.5]: https://example.com/repo/releases/tag/v1.2.5
"""


@pytest.fixture
def git_package(temp_toml_package: Path) -> Path:
    """temp_toml_package turned into a committed git repo with a CHANGELOG.md holding Unreleased entries."""
    (temp_toml_package / "CHANGELOG.md").write_text(CHANGELOG_WITH_ENTRIES, encoding="utf-8")
    cli.git(["init", "-q"], temp_toml_package)
    cli.git(["config", "user.email", "test@example.com"], temp_toml_package)
    cli.git(["config", "user.name", "Test"], temp_toml_package)
    cli.git(["add", "."], temp_toml_package)
    cli.git(["commit", "-q", "-m", "Initial"], temp_toml_package)
    return temp_toml_package


def _release_args(root: Path, bump: str = "minor", dry_run: bool = False) -> argparse.Namespace:
    return argparse.Namespace(root_dir=str(root), bump=bump, dry_run=dry_run)


def test_cmd_release_bumps_commits_and_tags(capsys, git_package: Path):
    rc = cli.cmd_release(_release_args(git_package, bump="minor"))
    assert rc == 0
    assert "1.2.5 -> 1.3.0" in capsys.readouterr().out
    assert tomlkit.parse((git_package / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"] == "1.3.0"
    assert read_init_version(git_package / "src") == "1.3.0"

    changelog = (git_package / "CHANGELOG.md").read_text(encoding="utf-8")
    assert f"## [Unreleased]\n\n## [1.3.0] - {cli.date.today():%Y-%m-%d}\n\n### Added\n- New thing." in changelog
    assert "[1.3.0]: https://example.com/repo/compare/v1.2.5...v1.3.0" in changelog

    assert cli.git(["log", "-1", "--format=%s"], git_package) == "Release v1.3.0"
    assert cli.git(["tag", "--points-at", "HEAD"], git_package) == "v1.3.0"
    assert cli.git_is_clean(git_package)


def test_cmd_release_dry_run_changes_nothing(git_package: Path):
    head = cli.git(["rev-parse", "HEAD"], git_package)
    rc = cli.cmd_release(_release_args(git_package, bump="major", dry_run=True))
    assert rc == 0
    assert cli.git(["rev-parse", "HEAD"], git_package) == head
    assert cli.git(["tag"], git_package) == ""
    assert "## [2.0.0]" not in (git_package / "CHANGELOG.md").read_text(encoding="utf-8")


def test_cmd_release_refuses_dirty_tree(git_package: Path):
    (git_package / "README.md").write_text("changed", encoding="utf-8")
    with pytest.raises(RuntimeError, match="uncommitted"):
        cli.cmd_release(_release_args(git_package))


def test_cmd_release_refuses_empty_unreleased(git_package: Path):
    (git_package / "CHANGELOG.md").write_text("# Changelog\n\n## [Unreleased]\n\n## [1.2.5] - 2026-01-01\n- x\n",
                                              encoding="utf-8")
    cli.git(["commit", "-q", "-a", "-m", "Empty unreleased"], git_package)
    with pytest.raises(ValueError, match="empty"):
        cli.cmd_release(_release_args(git_package))
    assert cli.git(["tag"], git_package) == ""


def test_resolve_build_dir_flag_overrides_config(monkeypatch, tmp_path):
    monkeypatch.setattr(cli.ConfigToml, "DEFAULT_PATH", tmp_path / "cfg" / "config.toml")
    cli.cmd_config(argparse.Namespace(action="set", key="build_dir", value=str(tmp_path / "cfg_build")))
    assert cli._resolve_build_dir(str(tmp_path / "flag_build")) == (tmp_path / "flag_build").resolve()


def test_resolve_build_dir_uses_config_build_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(cli.ConfigToml, "DEFAULT_PATH", tmp_path / "cfg" / "config.toml")
    cli.cmd_config(argparse.Namespace(action="set", key="build_dir", value=str(tmp_path / "cfg_build")))
    assert cli._resolve_build_dir(None) == (tmp_path / "cfg_build").resolve()


def test_resolve_build_dir_falls_back_to_local_build_folder(monkeypatch, tmp_path):
    monkeypatch.setattr(cli.ConfigToml, "DEFAULT_PATH", tmp_path / "no_such_config.toml")
    assert cli._resolve_build_dir(None) == Path(cli.DEFAULT_BUILD_DIR).resolve()


def test_cmd_build(tmp_path: Path, temp_toml_package: Path):
    dist_path = tmp_path / "dist"
    args = argparse.Namespace(root_dir=str(temp_toml_package), out_dir=str(dist_path))
    rc = cli.cmd_build(args)
    assert rc == 0
    assert any(dist_path.glob("*.whl"))  # check that wheel file is created


def _publish_args(source_path: Path, out_dir: Path, dry_run: bool, write_mod: bool = False) -> argparse.Namespace:
    return argparse.Namespace(source_path=str(source_path), out_dir=str(out_dir), channel="rel",
                              dry_run=dry_run, read_only=False, write_mod=write_mod)


@pytest.fixture
def fake_pip_install(monkeypatch):
    """Replaces cli.run so `pip install --target DST` just creates DST; records every command."""
    commands = []

    def _run(cmd, cwd=None):
        commands.append(cmd)
        if "--target" in cmd:
            Path(cmd[cmd.index("--target") + 1]).mkdir(parents=True)

    monkeypatch.setattr(cli, "run", _run)
    return commands


def test_cmd_publish_writes_metadata_file(tmp_path, fake_pip_install, temp_toml_package: Path):
    out_dir = tmp_path / "out"
    rc = cli.cmd_publish(_publish_args(temp_toml_package, out_dir, dry_run=False))
    assert rc == 0
    published = cli.PublishedVersion.from_folder(out_dir / "test_package" / "rel-1.2.5")
    assert published.label == "rel-1.2.5"
    assert (published.path / cli.METADATA_FILE).is_file()


def test_cmd_publish_write_mod_uses_maya_module_path(tmp_path, monkeypatch, fake_pip_install, temp_toml_package: Path):
    monkeypatch.setattr(cli.ConfigToml, "DEFAULT_PATH", tmp_path / "no_such_config.toml")
    mod_dir = tmp_path / "modules"
    mod_dir.mkdir()
    monkeypatch.setenv(cli.MAYA_MODULE_PATH_ENV, str(mod_dir))
    out_dir = tmp_path / "out"

    rc = cli.cmd_publish(_publish_args(temp_toml_package, out_dir, dry_run=False, write_mod=True))
    assert rc == 0
    mod_path = mod_dir / "test_package.mod"
    assert mod_path.read_text(encoding="utf-8").startswith(
        f"+ test_package 1.2.5 {(out_dir / 'test_package' / 'rel-1.2.5').resolve().as_posix()}")


def test_cmd_publish_write_mod_prefers_configured_mod_dir(tmp_path, monkeypatch, fake_pip_install, temp_toml_package: Path):
    monkeypatch.setattr(cli.ConfigToml, "DEFAULT_PATH", tmp_path / "cfg" / "config.toml")
    monkeypatch.setenv(cli.MAYA_MODULE_PATH_ENV, str(tmp_path / "env_modules"))
    configured = tmp_path / "cfg_modules"
    configured.mkdir()
    cli.cmd_config(argparse.Namespace(action="set", key="mod_dir", value=str(configured)))

    rc = cli.cmd_publish(_publish_args(temp_toml_package, tmp_path / "out", dry_run=False, write_mod=True))
    assert rc == 0
    assert (configured / "test_package.mod").is_file()


def test_cmd_publish_write_mod_fails_early_without_mod_dir(tmp_path, monkeypatch, fake_pip_install, temp_toml_package: Path):
    monkeypatch.setattr(cli.ConfigToml, "DEFAULT_PATH", tmp_path / "no_such_config.toml")
    monkeypatch.delenv(cli.MAYA_MODULE_PATH_ENV, raising=False)
    with pytest.raises(RuntimeError, match="mod_dir"):
        cli.cmd_publish(_publish_args(temp_toml_package, tmp_path / "out", dry_run=False, write_mod=True))
    assert not fake_pip_install  # nothing was installed


def test_cmd_publish_dev_channel_appends_commit_hash(tmp_path, monkeypatch, fake_pip_install, temp_toml_package: Path):
    monkeypatch.setattr(cli, "git_short_hash", lambda path: "abc1234")
    args = _publish_args(temp_toml_package, tmp_path / "out", dry_run=False)
    args.channel = "dev"
    assert cli.cmd_publish(args) == 0
    published = cli.PublishedVersion.from_folder(tmp_path / "out" / "test_package" / "dev-1.2.5+abc1234")
    assert published.commit == "abc1234"


def test_cmd_publish_rel_channel_keeps_plain_version(tmp_path, monkeypatch, fake_pip_install, temp_toml_package: Path):
    monkeypatch.setattr(cli, "git_short_hash", lambda path: "abc1234")
    assert cli.cmd_publish(_publish_args(temp_toml_package, tmp_path / "out", dry_run=False)) == 0
    assert (tmp_path / "out" / "test_package" / "rel-1.2.5").is_dir()


def test_cmd_publish_dev_channel_without_git_keeps_plain_version(tmp_path, monkeypatch, fake_pip_install, temp_toml_package: Path):
    monkeypatch.setattr(cli, "git_short_hash", lambda path: None)
    args = _publish_args(temp_toml_package, tmp_path / "out", dry_run=False)
    args.channel = "dev"
    assert cli.cmd_publish(args) == 0
    assert (tmp_path / "out" / "test_package" / "dev-1.2.5").is_dir()


def test_publish_dry_run_prints_target(tmp_path, capsys, temp_toml_package: Path):
    out_dir = tmp_path / "out"
    rc = cli.cmd_publish(_publish_args(temp_toml_package, out_dir, dry_run=True))
    assert rc == 0
    assert (out_dir / "test_package" / "rel-1.2.5").as_posix() in capsys.readouterr().out
    assert not out_dir.exists()


def test_publish_refuses_existing_target(tmp_path, temp_toml_package: Path):
    out_dir = tmp_path / "out"
    (out_dir / "test_package" / "rel-1.2.5").mkdir(parents=True)
    with pytest.raises(FileExistsError):
        cli.cmd_publish(_publish_args(temp_toml_package, out_dir, dry_run=False))


def test_resolve_publish_out_dir_flag_overrides_env_and_config(monkeypatch, tmp_path):
    monkeypatch.setattr(cli.ConfigToml, "DEFAULT_PATH", tmp_path / "unused_config.toml")
    monkeypatch.setenv("DLPKG_PUBLISH_DIR", str(tmp_path / "env_dir"))
    flag_dir = tmp_path / "flag_dir"
    assert cli._resolve_publish_out_dir(str(flag_dir)) == flag_dir.resolve()


def test_resolve_publish_out_dir_env_var_used_when_no_flag(monkeypatch, tmp_path):
    monkeypatch.setattr(cli.ConfigToml, "DEFAULT_PATH", tmp_path / "unused_config.toml")
    env_dir = tmp_path / "env_dir"
    monkeypatch.setenv("DLPKG_PUBLISH_DIR", str(env_dir))
    assert cli._resolve_publish_out_dir(None) == env_dir.resolve()


def test_resolve_publish_out_dir_uses_config_publish_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(cli.ConfigToml, "DEFAULT_PATH", tmp_path / "cfg" / "config.toml")
    monkeypatch.delenv("DLPKG_PUBLISH_DIR", raising=False)
    config_dir = tmp_path / "configured_publishes"
    config = cli.ConfigToml.open_default()
    config.publish_dir = config_dir
    config.save()

    assert cli._resolve_publish_out_dir(None) == config_dir.resolve()


def test_resolve_publish_out_dir_falls_back_to_local_publish_folder(monkeypatch, tmp_path):
    monkeypatch.setattr(cli.ConfigToml, "DEFAULT_PATH", tmp_path / "no_such_config.toml")
    monkeypatch.delenv("DLPKG_PUBLISH_DIR", raising=False)
    assert cli._resolve_publish_out_dir(None) == Path(cli.DEFAULT_PUBLISH_DIR).resolve()


def test_cmd_publish_uses_configured_publish_dir_when_no_out_dir_flag(monkeypatch, tmp_path, capsys, temp_toml_package: Path):
    monkeypatch.setattr(cli.ConfigToml, "DEFAULT_PATH", tmp_path / "cfg" / "config.toml")
    monkeypatch.delenv("DLPKG_PUBLISH_DIR", raising=False)
    config_dir = tmp_path / "configured_publishes"
    config = cli.ConfigToml.open_default()
    config.publish_dir = config_dir
    config.save()

    args = argparse.Namespace(source_path=str(temp_toml_package), out_dir=None, channel="rel", dry_run=True,
                              read_only=False, write_mod=False)
    rc = cli.cmd_publish(args)
    assert rc == 0
    out = capsys.readouterr().out
    assert config_dir.resolve().as_posix() in out
    assert not (tmp_path / "publish").exists()  # never touches the ./publish fallback


def test_cmd_list_basic(capsys, published_versions_dir):
    args = argparse.Namespace(package_name="my_package", dir=str(published_versions_dir), limit=None)
    rc = cli.cmd_list(args)
    assert rc == 0
    out = capsys.readouterr().out
    assert "Published versions (latest 10):" in out
    assert "Development versions (latest 10):" in out
    # semver order, not string order (2.0.0 > 1.10.0 > 1.9.0 > 1.2.5 > 1.0.0)
    rel_lines = [line for line in out.splitlines() if line.startswith("    rel-")]
    rel_labels = [line.split()[0] for line in rel_lines]
    assert rel_labels == ["rel-2.0.0", "rel-1.10.0", "rel-1.9.0", "rel-1.2.5", "rel-1.0.0"]
    assert all(re.search(r"\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}\]", line) for line in rel_lines)
    assert any(line.startswith("    dev-2.0.0-beta.1") for line in out.splitlines())
    assert any(line.startswith("    dev-1.2.3-alpha.1") for line in out.splitlines())
    assert "not-a-valid-format-here" not in out
    assert "not-semver" not in out


def test_cmd_list_truncates_to_latest_10(tmp_path, capsys):
    pkg_dir = tmp_path / "publishes" / "my_package"
    pkg_dir.mkdir(parents=True)
    for i in range(15):
        (pkg_dir / f"rel-1.{i}.0").mkdir()
    args = argparse.Namespace(package_name="my_package", dir=str(tmp_path / "publishes"), limit=None)
    rc = cli.cmd_list(args)
    assert rc == 0
    out = capsys.readouterr().out
    rel_lines = [l for l in out.splitlines() if l.startswith("    rel-")]
    assert len(rel_lines) == 10
    assert "rel-1.14.0" in rel_lines[0]
    assert not any("1.4.0" in l for l in rel_lines)  # only top 10 of 15 kept


def test_cmd_list_missing_folder_is_empty(tmp_path, capsys):
    args = argparse.Namespace(package_name="ghost_pkg", dir=str(tmp_path / "does_not_exist"), limit=None)
    rc = cli.cmd_list(args)
    assert rc == 0
    out = capsys.readouterr().out
    assert not any(l.startswith("    rel-") or l.startswith("    dev-") for l in out.splitlines())


def test_cmd_list_requires_package_name(tmp_path):
    args = argparse.Namespace(package_name=None, dir=str(tmp_path), limit=None)
    with pytest.raises(RuntimeError, match="package_name"):
        cli.cmd_list(args)


@pytest.fixture
def maya_mod_dir(tmp_path, monkeypatch):
    """An empty Maya modules folder on MAYA_MODULE_PATH, with config.toml pointed at nothing."""
    monkeypatch.setattr(cli.ConfigToml, "DEFAULT_PATH", tmp_path / "no_such_config.toml")
    mod_dir = tmp_path / "modules"
    mod_dir.mkdir()
    monkeypatch.setenv(cli.MAYA_MODULE_PATH_ENV, str(mod_dir))
    return mod_dir


def test_cmd_use_writes_mod_file(capsys, maya_mod_dir, published_versions_dir):
    args = argparse.Namespace(package_name="my_package", version="rel-1.9.0", dir=str(published_versions_dir))
    rc = cli.cmd_use(args)
    assert rc == 0
    target = (published_versions_dir / "my_package" / "rel-1.9.0").resolve()
    assert cli.read_mod_target(maya_mod_dir / "my_package.mod") == target
    assert "rel-1.9.0" in capsys.readouterr().out


def test_cmd_use_switches_between_versions(maya_mod_dir, published_versions_dir):
    for label in ["rel-2.0.0", "dev-1.2.3-alpha.1"]:
        cli.cmd_use(argparse.Namespace(package_name="my_package", version=label, dir=str(published_versions_dir)))
    assert cli.read_mod_target(maya_mod_dir / "my_package.mod") == \
        (published_versions_dir / "my_package" / "dev-1.2.3-alpha.1").resolve()


def test_cmd_use_unpublished_version_raises(maya_mod_dir, published_versions_dir):
    args = argparse.Namespace(package_name="my_package", version="rel-9.9.9", dir=str(published_versions_dir))
    with pytest.raises(FileNotFoundError):
        cli.cmd_use(args)
    assert not (maya_mod_dir / "my_package.mod").exists()


def test_cmd_list_marks_active_version(capsys, maya_mod_dir, published_versions_dir):
    cli.cmd_use(argparse.Namespace(package_name="my_package", version="rel-1.9.0", dir=str(published_versions_dir)))
    capsys.readouterr()

    rc = cli.cmd_list(argparse.Namespace(package_name="my_package", dir=str(published_versions_dir), limit=None))
    assert rc == 0
    marked = [l for l in capsys.readouterr().out.splitlines() if cli.ACTIVE_MARKER in l]
    assert len(marked) == 1
    assert marked[0].startswith("    rel-1.9.0")


def test_cmd_list_without_mod_file_has_no_active_marker(capsys, maya_mod_dir, published_versions_dir):
    rc = cli.cmd_list(argparse.Namespace(package_name="my_package", dir=str(published_versions_dir), limit=None))
    assert rc == 0
    assert cli.ACTIVE_MARKER not in capsys.readouterr().out


def _prune_args(published_dir: Path, channel: str = "rel", keep: int = 2, dry_run: bool = False) -> argparse.Namespace:
    return argparse.Namespace(package_name="my_package", channel=channel, keep=keep, dir=str(published_dir),
                              dry_run=dry_run)


def _rel_folders(published_dir: Path) -> list[str]:
    return sorted(p.name for p in (published_dir / "my_package").iterdir() if p.name.startswith("rel-"))


def test_cmd_prune_keeps_newest(maya_mod_dir, published_versions_dir):
    rc = cli.cmd_prune(_prune_args(published_versions_dir, keep=2))
    assert rc == 0
    assert _rel_folders(published_versions_dir) == ["rel-1.10.0", "rel-2.0.0", "rel-not-semver"]
    assert (published_versions_dir / "my_package" / "dev-1.2.3-alpha.1").is_dir()  # other channel untouched


def test_cmd_prune_never_removes_active(maya_mod_dir, published_versions_dir):
    cli.cmd_use(argparse.Namespace(package_name="my_package", version="rel-1.0.0", dir=str(published_versions_dir)))
    rc = cli.cmd_prune(_prune_args(published_versions_dir, keep=1))
    assert rc == 0
    assert _rel_folders(published_versions_dir) == ["rel-1.0.0", "rel-2.0.0", "rel-not-semver"]


def test_cmd_prune_dry_run_deletes_nothing(capsys, maya_mod_dir, published_versions_dir):
    before = _rel_folders(published_versions_dir)
    rc = cli.cmd_prune(_prune_args(published_versions_dir, keep=1, dry_run=True))
    assert rc == 0
    assert _rel_folders(published_versions_dir) == before
    assert "rel-1.0.0" in capsys.readouterr().out


def test_cmd_prune_removes_read_only_files(maya_mod_dir, published_versions_dir):
    victim = published_versions_dir / "my_package" / "rel-1.0.0"
    locked = victim / "locked.txt"
    locked.write_text("x", encoding="utf-8")
    locked.chmod(0o444)
    rc = cli.cmd_prune(_prune_args(published_versions_dir, keep=1))
    assert rc == 0
    assert not victim.exists()


def test_cmd_prune_nothing_to_do(capsys, maya_mod_dir, published_versions_dir):
    rc = cli.cmd_prune(_prune_args(published_versions_dir, keep=10))
    assert rc == 0
    assert "Nothing to prune" in capsys.readouterr().out


def test_cmd_config_set_publish_dir_then_used_by_list(tmp_path, monkeypatch, capsys, published_versions_dir):
    monkeypatch.setattr(cli.ConfigToml, "DEFAULT_PATH", tmp_path / "cfg" / "config.toml")
    monkeypatch.delenv("DLPKG_PUBLISH_DIR", raising=False)

    set_args = argparse.Namespace(action="set", key="publish_dir", value=str(published_versions_dir))
    rc = cli.cmd_config(set_args)
    assert rc == 0
    assert (tmp_path / "cfg" / "config.toml").exists()

    list_args = argparse.Namespace(package_name="my_package", dir=None, limit=None)
    rc2 = cli.cmd_list(list_args)
    assert rc2 == 0
    assert "rel-2.0.0" in capsys.readouterr().out


def test_cmd_config_get_unset_key_returns_1(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(cli.ConfigToml, "DEFAULT_PATH", tmp_path / "cfg" / "config.toml")
    args = argparse.Namespace(action="get", key="nope")
    rc = cli.cmd_config(args)
    assert rc == 1
    assert "not set" in capsys.readouterr().out


def test_cmd_config_set_then_get_roundtrip(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(cli.ConfigToml, "DEFAULT_PATH", tmp_path / "cfg" / "config.toml")
    set_args = argparse.Namespace(action="set", key="publish_dir", value=str(tmp_path / "publishes"))
    assert cli.cmd_config(set_args) == 0
    capsys.readouterr()

    get_args = argparse.Namespace(action="get", key="publish_dir")
    assert cli.cmd_config(get_args) == 0
    out = capsys.readouterr().out.strip()
    assert out == str((tmp_path / "publishes").resolve())


def test_cmd_config_list_prints_key_value_lines(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(cli.ConfigToml, "DEFAULT_PATH", tmp_path / "cfg" / "config.toml")
    cli.cmd_config(argparse.Namespace(action="set", key="publish_dir", value=str(tmp_path / "publishes")))
    cli.cmd_config(argparse.Namespace(action="set", key="list_limit", value="5"))
    capsys.readouterr()

    rc = cli.cmd_config(argparse.Namespace(action="list"))
    assert rc == 0
    out = capsys.readouterr().out
    assert f"publish_dir = {(tmp_path / 'publishes').resolve()}" in out
    assert "list_limit = 5" in out


def test_cmd_config_list_empty_says_no_settings(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(cli.ConfigToml, "DEFAULT_PATH", tmp_path / "cfg" / "config.toml")
    rc = cli.cmd_config(argparse.Namespace(action="list"))
    assert rc == 0
    assert "no settings configured" in capsys.readouterr().out


def test_cmd_list_dir_flag_overrides_env_and_config(monkeypatch, tmp_path, published_versions_dir):
    monkeypatch.setattr(cli.ConfigToml, "DEFAULT_PATH", tmp_path / "unused_config.toml")
    monkeypatch.setenv("DLPKG_PUBLISH_DIR", str(tmp_path / "env_dir"))
    args = argparse.Namespace(package_name="my_package", dir=str(published_versions_dir), limit=None)
    assert cli.cmd_list(args) == 0  # doesn't error even though env/config point elsewhere


def test_cmd_list_env_var_used_when_no_dir_flag(monkeypatch, tmp_path, published_versions_dir):
    monkeypatch.setattr(cli.ConfigToml, "DEFAULT_PATH", tmp_path / "unused_config.toml")
    monkeypatch.setenv("DLPKG_PUBLISH_DIR", str(published_versions_dir))
    args = argparse.Namespace(package_name="my_package", dir=None, limit=None)
    assert cli.cmd_list(args) == 0


def test_cmd_list_raises_if_no_dir_env_or_config(monkeypatch, tmp_path):
    monkeypatch.setattr(cli.ConfigToml, "DEFAULT_PATH", tmp_path / "no_such_config.toml")
    monkeypatch.delenv("DLPKG_PUBLISH_DIR", raising=False)
    args = argparse.Namespace(package_name="my_package", dir=None, limit=None)
    with pytest.raises(RuntimeError, match="DLPKG_PUBLISH_DIR"):
        cli.cmd_list(args)


def test_cmd_list_limit_flag_overrides_config(monkeypatch, tmp_path, published_versions_dir):
    monkeypatch.setattr(cli.ConfigToml, "DEFAULT_PATH", tmp_path / "cfg" / "config.toml")
    config = cli.ConfigToml.open_default()
    config.set_value("list_limit", 2)
    config.save()

    args = argparse.Namespace(package_name="my_package", dir=str(published_versions_dir), limit=1)
    rc = cli.cmd_list(args)
    assert rc == 0


def test_cmd_list_uses_configured_list_limit_when_no_flag(monkeypatch, capsys, tmp_path, published_versions_dir):
    monkeypatch.setattr(cli.ConfigToml, "DEFAULT_PATH", tmp_path / "cfg" / "config.toml")
    config = cli.ConfigToml.open_default()
    config.set_value("list_limit", 2)
    config.save()

    args = argparse.Namespace(package_name="my_package", dir=str(published_versions_dir), limit=None)
    rc = cli.cmd_list(args)
    assert rc == 0
    out = capsys.readouterr().out
    assert "latest 2" in out
    rel_lines = [l for l in out.splitlines() if l.startswith("    rel-")]
    assert len(rel_lines) == 2
