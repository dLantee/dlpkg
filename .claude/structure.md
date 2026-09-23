# dlpkg structure

```
src/dlpkg/
    cli.py          argparse tree plus every cmd_* subcommand; no dispatch layer
    changelog.py    release_changelog(): dates the Unreleased section and repoints compare links
    package.py      PythonPackage facade: name, version, authors, source dirs
    published.py    CHANNELS, PublishedVersion, scan_published(), find_published(), remove_published(), write_metadata()
    tomlutil.py     TomlFile base, PyProjectToml, ConfigToml, PublishToml (tomlkit)
    versioning.py   SemVer dataclass, read_init_version() and write_init_version() for __init__.py
    util.py         run, git, git_short_hash, git_is_clean, ensure_empty_dir, make_read_only_recursively (icacls)
    modfile.py      Maya .mod files: first_maya_module_dir(), write_mod_file(), read_mod_target()
tests/              pytest suite, fixtures in conftest.py, see .claude/testing.md
config.toml         persisted defaults, read by ConfigToml
pyproject.toml      [tool.pytest.ini_options] puts src on the test path
```

## Key behaviour

- `cmd_publish` takes a package root or a `.whl` path (`_package_source`). From a wheel it parses
  name and version out of the filename with `_WHEEL_NAME_RE`. For a root dir the published name is
  the folder name (`PythonPackage.name`), not `[project].name`. The target
  `<out_dir>/<name>/<channel>-<version>` must not exist yet. A `DEV_CHANNEL` publish from a package
  root gets the git short hash appended as build metadata (`with_build_tag`); wheels are never retagged.
- Output folder precedence lives in one helper, `_configured_publish_dir`: CLI flag, then
  `PUBLISH_DIR_ENV`, then `ConfigToml.publish_dir`. `cmd_publish` falls back to
  `DEFAULT_PUBLISH_DIR`; `cmd_list` raises instead.
- `published.CHANNELS` maps channel name to the heading `cmd_list` prints and drives the `--channel`
  choices. `scan_published` returns `{channel: [PublishedVersion, ...]}` newest-first, cut to
  `--limit`, config `list_limit`, or `DEFAULT_LIST_LIMIT`. Every published folder carries a
  `METADATA_FILE` (`dlpkg.toml`, a `PublishToml`) with the publish time and git commit; folders
  without one fall back to the filesystem creation time.
- `cmd_config get|set|list` is the only supported way to persist settings in `config.toml`.
- `cmd_release` follows `D:\Dev\.claude\git-workflow.md`: clean tree required, `PythonPackage.version`
  bump, `release_changelog`, `git add --update`, commit `RELEASE_COMMIT_FORMAT`, annotated tag. No push.
- `_resolve_build_dir`: `--out-dir` flag, then config `build_dir`, then `DEFAULT_BUILD_DIR`. Config path
  keys resolve relative to `config.toml`, so a relative `build_dir` there points into the dlpkg repo.
- `PythonPackage` reads the version from `pyproject.toml` first, then `__version__` in `__init__.py`.
  Setting it always writes `pyproject.toml`; the `__init__.py` write is best effort and skipped
  when no `__init__.py` defines `__version__`. Without `pyproject.toml` every accessor raises.
- `PyProjectToml.source_roots` finds the source dir the way setuptools does: `packages.find.where`,
  else `package-dir` `""`, else the pyproject directory. Only existing dirs are returned.
- `SemVer` equality and hash both ignore build metadata.
- `publish --write-mod` writes `<name>.mod` with `+ <name> <version> <folder>` and `PYTHONPATH +:= .`
  (pip `--target` puts the package right inside the version folder). The mod folder comes from
  `_resolve_mod_dir`: config `mod_dir`, else the first existing dir on `MAYA_MODULE_PATH`.
  `cmd_use` rewrites the same file to an existing published folder found by `find_published`.
  `cmd_list` and `cmd_prune` read it back through `_active_mod_target`; prune never deletes that folder.

## Conventions

- `cmd_*` functions take an `argparse.Namespace` and return an `int` exit code. Tests call them
  directly with a hand-built `Namespace`.
- Positional `root_dir` / `source_path` defaults to `.`, so commands run from inside the target package.
- `CMD_FORMAT` in `cli.py` holds raw ANSI codes; no colour library.
- Defaults, env var names and config keys are module constants, never inline literals.
- Missing TOML keys are caught with `(KeyError, TypeError)`; tomlkit's `NonExistentKey` is a `KeyError`.
