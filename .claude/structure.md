# dlpkg structure

```
src/dlpkg/
    cli.py          argparse tree plus every cmd_* subcommand; no dispatch layer
    package.py      PythonPackage facade: name, version, authors, source dirs
    tomlutil.py     TomlFile base, PyProjectToml, ConfigToml (tomlkit)
    versioning.py   SemVer dataclass, read_init_version() and write_init_version() for __init__.py
    util.py         run, ensure_empty_dir, make_read_only_recursively (icacls, Windows only)
    modfile.py      untracked, in-progress Maya .mod writer (main checkout only)
tests/              pytest suite, fixtures in conftest.py, see .claude/testing.md
config.toml         persisted defaults, read by ConfigToml
pyproject.toml      [tool.pytest.ini_options] puts src on the test path
```

## Key behaviour

- `cmd_publish` takes a package root or a `.whl` path (`_package_source`). From a wheel it parses
  name and version out of the filename with `_WHEEL_NAME_RE`. For a root dir the published name is
  the folder name (`PythonPackage.name`), not `[project].name`. The target
  `<out_dir>/<name>/<channel>-<version>` must not exist yet.
- Output folder precedence lives in one helper, `_configured_publish_dir`: CLI flag, then
  `PUBLISH_DIR_ENV`, then `ConfigToml.publish_dir`. `cmd_publish` falls back to
  `DEFAULT_PUBLISH_DIR`; `cmd_list` raises instead.
- `CHANNELS` maps channel name to the heading `cmd_list` prints and drives the `--channel` choices.
  `_scan_published_versions` returns `{channel: [(SemVer, datetime), ...]}` newest-first, cut to
  `--limit`, config `list_limit`, or `DEFAULT_LIST_LIMIT`. The datetime is the folder's creation
  time; no metadata file is written.
- `cmd_config get|set|list` is the only supported way to persist settings in `config.toml`.
- `cmd_build --out-dir` defaults to `DEFAULT_BUILD_DIR`, not wired to `ConfigToml.build_dir`.
- `PythonPackage` reads the version from `pyproject.toml` first, then `__version__` in `__init__.py`.
  Setting it always writes `pyproject.toml`; the `__init__.py` write is best effort and skipped
  when no `__init__.py` defines `__version__`. Without `pyproject.toml` every accessor raises.
- `PyProjectToml.source_roots` finds the source dir the way setuptools does: `packages.find.where`,
  else `package-dir` `""`, else the pyproject directory. Only existing dirs are returned.
- `SemVer` equality and hash both ignore build metadata.
- `modfile.py` is not wired up. `cli.py` keeps a commented-out `base_parser`, `--write-mod` flag and
  `writemod` subcommand stub showing the intended shape. Leave them in place.

## Conventions

- `cmd_*` functions take an `argparse.Namespace` and return an `int` exit code. Tests call them
  directly with a hand-built `Namespace`.
- Positional `root_dir` / `source_path` defaults to `.`, so commands run from inside the target package.
- `CMD_FORMAT` in `cli.py` holds raw ANSI codes; no colour library.
- Defaults, env var names and config keys are module constants, never inline literals.
- Missing TOML keys are caught with `(KeyError, TypeError)`; tomlkit's `NonExistentKey` is a `KeyError`.
