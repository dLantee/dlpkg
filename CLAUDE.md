# dlpkg

## Overrides

- Tests use `pytest` (overrides the `tools/` default of `unittest`). See Tests below.

## What this is

`dlpkg` is a Python CLI tool (installed as the `dlpkg` command via `[project.scripts]`) for managing
*other* Python packages' development lifecycle: `version` (read/bump semver) → `build` (wheel via `python -m
build`) → `publish` (copy into a versioned target dir via `pip install --target`). It is not a build backend
itself. It shells out to `pip`/`build` and edits `pyproject.toml` / `__init__.py` directly.

Requires Python >=3.13. Runtime dependency: `tomlkit` (all TOML reading/writing must preserve formatting/comments,
so use `tomlkit`, not `tomllib`/`toml`).

## Common commands

```commandline
py -m pip install -e .          # install dlpkg locally for development (editable)
dlpkg version [root_dir]        # print current version
dlpkg version --bump patch      # bump patch/minor/major/prerelease
dlpkg build --out-dir DIR       # build wheel+sdist via `python -m build`
dlpkg publish --out-dir DIR     # publish into DIR/<name>/<channel>-<version>/ (or config.toml's
                                 # publish_dir / DLPKG_PUBLISH_DIR if --out-dir is omitted; falls
                                 # back to ./publish if none of those are set)
dlpkg list <name> --dir DIR     # list published rel-*/dev-* versions under DIR/<name>/, with
                                 # each version's publish timestamp
dlpkg config set publish_dir DIR # persist a default publish/list folder in config.toml
```

There is no configured lint/typecheck command (no ruff/mypy config present).

### Tests

Tests use `pytest`. It's installed in the active venv (`D:\Dev\venvs\python313`) but **not** in `py -3.10` or
`py -3.14`. Install it first (`pip install pytest`) in whichever environment you're testing with. There's no
`pytest.ini`/`tox.ini`/dev-requirements file; pytest config is entirely default.

Tests import shared fixtures with a bare `from fixtures import temp_toml_package` (not a relative import).
`tests/__init__.py` exists (empty) so `tests/` is a package. This means pytest's default `prepend` import mode
adds the *parent* of `tests/` (repo root) to `sys.path`, not `tests/` itself, so the bare `fixtures` import does
**not** resolve with a plain `pytest` invocation (confirmed: raises `ModuleNotFoundError: No module named
'fixtures'`). Put `tests/` on `PYTHONPATH` explicitly:

```commandline
PYTHONPATH=tests pytest                          # run all tests (bash/git-bash)
PYTHONPATH=tests pytest tests/test_versioning.py  # run a single test file
PYTHONPATH=tests pytest tests/test_versioning.py::test_bump  # run a single test
```
(On PowerShell: `$env:PYTHONPATH = "tests"; pytest`.) Don't add relative imports to `fixtures`. That would
break under this setup too.

**Known-broken tests** (pre-existing, verified via `git stash`, not a spec for current behavior):
- `tests/test_publisher.py` imports `from dlpkg.publisher import publish_folder`, but `publisher.py` was
  deleted in the 0.3.0 refactor (its logic moved into `cli.py`'s `cmd_publish`), fails on collection.
- `test_publish_basic` (`test_cli.py`) builds its `argparse.Namespace` with `root_dir=...`, but `cmd_publish`
  reads `args.source_path`, fails with `AttributeError`.
- `test_update_args_from_files_publish_out_dir_uses_config_publish_dir`,
  `..._falls_back_to_maya_module_path`, `..._raises_if_no_config_and_no_env` (`test_cli.py`) all reference
  `cli._get_pyproject_doc` / `cli._get_config_doc` / `cli._update_args_from_files`, none of which exist in
  current `cli.py`, fail with `AttributeError`.

## Architecture

**`cli.py`**: argparse entry point (`main()`) and all subcommand implementations (`cmd_version`,
`cmd_build`, `cmd_publish`, `cmd_list`, `cmd_config`) live directly in this module; there's no separate
command-dispatch layer. `cmd_publish` accepts either a package root dir (containing `pyproject.toml`) or a
`.whl` file path directly. When given a wheel, it parses `name`/`version` out of the filename with a regex
instead of reading package metadata. `cmd_publish`'s target root folder (`--out-dir`) is resolved via
`_resolve_publish_out_dir`: `--out-dir` flag → `DLPKG_PUBLISH_DIR` env var → `ConfigToml.publish_dir`
(config.toml) → `./publish` (hardcoded local fallback, `DEFAULT_PUBLISH_DIR`), the same precedence chain as
`cmd_list` below, except it falls back to a default instead of raising when nothing is configured.

`cmd_list` scans `<folder>/<package_name>/rel-*` and `dev-*` subdirectories (the same layout `cmd_publish`
writes), parses each version with `SemVer.parse`, and prints the latest 10 per channel alongside each
version's publish timestamp. The folder is resolved via `_resolve_list_dir`: `--dir` flag →
`DLPKG_PUBLISH_DIR` env var → `ConfigToml.publish_dir` (config.toml), in that order (raises if none are set,
unlike `_resolve_publish_out_dir`). `_scan_published_versions` returns `(SemVer, datetime)` pairs per
channel. The `datetime` is the version folder's filesystem creation time (`Path.stat().st_ctime`, accurate
on Windows/NTFS since `cmd_publish` creates each folder fresh via `pip install --target`); no metadata file
is written for this. `_format_list_line` renders each pair as `    rel-1.2.5             [2026-07-15 14:32]`.

`cmd_config` implements `dlpkg config get|set|list` (git-config style) against `config.toml`'s `[defaults]`
table via the generic `ConfigToml.get_value`/`set_value`/`all_values` methods. This is the only supported
way to persist settings other than hand-editing `config.toml` directly (the old `dlpkg list
--set-default-dir` flag was removed in favor of it).

**`package.py`** (`PythonPackage`): the main facade other modules use to query/mutate a package under
development: name, version (get/set), authors, source dirs. It tries `pyproject.toml` first via
`tomlutil.PyProjectToml`, and falls back to parsing `__version__` out of `__init__.py` (via `versioning.
init_version`) when `pyproject.toml` has no `[project].version`. When *setting* the version, it writes to both
locations if both exist, so version stays in sync across `pyproject.toml` and `__init__.py`.

**`tomlutil.py`**: `TomlFile` is a thin base wrapper around `tomlkit` for load/save-in-place with dict-like
access. `PyProjectToml` (subclass) adds typed accessors for `[project]` fields and, notably,
`source_roots`: it derives the actual source directory (or directories) for *the target package* by reading
`[tool.setuptools.packages.find].where`, falling back to `[tool.setuptools.package-dir]`'s `""` key, then to
`src`/`python` if those exist, mirroring how setuptools itself resolves package roots. This is the crux of how
dlpkg locates the package under management without needing a `--source-dir` flag in most cases.

`ConfigToml` (also in this file) reads/writes `config.toml` at the repo root (renamed from
`default_paths.toml`; `ConfigToml.DEFAULT_PATH` resolves three parents up from `tomlutil.py`, i.e.
`src/dlpkg/tomlutil.py` → repo root). Its `build_dir`/`publish_dir` properties now match the file's actual
keys and return `None` (not raise) when unset, so callers can fall through a precedence chain.
`ConfigToml.publish_dir` is now consumed by both `cmd_list` (via `_resolve_list_dir`) and `cmd_publish` (via
`_resolve_publish_out_dir`) as a shared default for "where published packages live"; `dlpkg config set
publish_dir PATH` writes it. `cmd_build`'s `--out-dir` is the one holdout still hardcoded to `./build` and
not wired to `ConfigToml.build_dir`. `util.is_git_repo` still exists but is unused anywhere in `cli.py`.

**`versioning.py`**: `SemVer` (frozen dataclass, `@total_ordering`) implements strict semver parsing/comparison/
bumping, including correct prerelease precedence rules (numeric identifiers compare numerically, no-prerelease >
prerelease, etc). `init_version()` is a standalone function (not a method) that both reads and writes
`__version__ = "..."` in a package's `__init__.py` via regex. The same function handles both directions depending
on whether `new_version` is passed.

**`modfile.py`** (untracked, in-progress feature): helpers for writing Autodesk Maya `.mod` module descriptor
files (`_write_mod_file`) so a package published by `dlpkg publish` can also register itself on
`MAYA_MODULE_PATH`. Not yet wired up: `cli.py` has a commented-out `--write-mod` flag and `writemod` subcommand
stub referencing this module. If asked to finish this feature, the intended shape is visible in those comments
in `cli.py`.

## Notable conventions

- Subcommand functions (`cmd_*`) take `argparse.Namespace` and return an `int` exit code; `main()` does
  `int(args.func(args))`. Tests call `cmd_*` functions directly with a hand-built `argparse.Namespace` rather than
  invoking through `main()`/`sys.argv`.
- All positional `root_dir`/`source_path` args default to `.` (current directory): every subcommand is meant to
  be run from inside the target package by default, with the positional arg as an override.
- `CMD_FORMAT` in `cli.py` holds raw ANSI escape codes for colored terminal output (no external color library).
