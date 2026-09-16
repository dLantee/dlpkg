# dlpkg Structure

A Python CLI for managing *other* packages' development lifecycle: read or bump the version,
build a wheel, publish it into a versioned folder. It is not a build backend. It shells out to
`pip` and `build`, and edits `pyproject.toml` and `__init__.py` directly. All TOML goes through
`tomlkit` so formatting and comments survive a round trip.

## Structure

```
src/dlpkg/
    cli.py              argparse entry point and every subcommand
    package.py          PythonPackage facade over a package under development
    tomlutil.py         tomlkit wrappers: TomlFile, PyProjectToml, ConfigToml
    versioning.py       SemVer and __init__.py version read/write
    util.py             is_git_repo, unused by cli.py
    modfile.py          untracked, in-progress Maya .mod writer
tests/                  pytest suite, see .claude/testing.md
config.toml             persisted defaults, read by ConfigToml
pyproject.toml          dlpkg's own metadata, [project.scripts] installs the dlpkg command
```

## Files

### `cli.py`
`main()` builds the argparse tree; `cmd_version`, `cmd_build`, `cmd_publish`, `cmd_list` and
`cmd_config` live in this module. There is no separate command-dispatch layer.

- `cmd_publish` accepts either a package root dir (containing `pyproject.toml`) or a `.whl` path.
  Given a wheel, it parses `name` and `version` out of the filename with a regex instead of reading
  package metadata. The target root folder comes from `_resolve_publish_out_dir`: the `--out-dir`
  flag, then the `DLPKG_PUBLISH_DIR` env var, then `ConfigToml.publish_dir`, then the hardcoded
  `./publish` (`DEFAULT_PUBLISH_DIR`). Same chain as `cmd_list`, except it falls back instead of
  raising.
- `cmd_list` scans `<folder>/<package_name>/rel-*` and `dev-*` (the layout `cmd_publish` writes),
  parses each with `SemVer.parse`, and prints the latest 10 per channel with a publish timestamp.
  The folder comes from `_resolve_list_dir`: `--dir` flag, then `DLPKG_PUBLISH_DIR`, then
  `ConfigToml.publish_dir`; it raises if none are set. `_scan_published_versions` returns
  `(SemVer, datetime)` pairs per channel. The datetime is the folder's creation time
  (`Path.stat().st_ctime`, accurate on NTFS because `pip install --target` creates each folder
  fresh); no metadata file is written. `_format_list_line` renders
  `    rel-1.2.5             [2026-07-15 14:32]`.
- `cmd_config` implements `dlpkg config get|set|list` (git-config style) against `config.toml`'s
  `[defaults]` table through `ConfigToml.get_value`, `set_value` and `all_values`. It is the only
  supported way to persist settings besides hand-editing `config.toml`; the old
  `dlpkg list --set-default-dir` flag was removed in its favour.
- `cmd_build`'s `--out-dir` is still hardcoded to `./build`, not wired to `ConfigToml.build_dir`.

### `package.py`
`PythonPackage` is the facade other modules use to query or mutate a package under development:
name, version (get/set), authors, source dirs. It tries `pyproject.toml` first via
`tomlutil.PyProjectToml`, and falls back to `__version__` in `__init__.py` (via
`versioning.init_version`) when `pyproject.toml` has no `[project].version`. Setting the version
writes to both locations if both exist, keeping them in sync.

### `tomlutil.py`
- `TomlFile`: thin base over `tomlkit` for load and save-in-place with dict-like access.
- `PyProjectToml`: typed accessors for `[project]` fields, plus `source_roots`, which derives the
  target package's source directory the way setuptools does: `[tool.setuptools.packages.find].where`,
  then `[tool.setuptools.package-dir]`'s `""` key, then `src` or `python` if they exist. This is
  why dlpkg rarely needs a `--source-dir` flag.
- `ConfigToml`: reads and writes `config.toml` at the repo root (`DEFAULT_PATH` resolves three
  parents up from `tomlutil.py`). `build_dir` and `publish_dir` return `None` when unset so callers
  can fall through a precedence chain. `publish_dir` is shared by `cmd_list` and `cmd_publish`;
  `dlpkg config set publish_dir PATH` writes it.

### `versioning.py`
`SemVer` is a frozen `@total_ordering` dataclass implementing strict semver parsing, comparison and
bumping, including prerelease precedence (numeric identifiers compare numerically, no prerelease
sorts above prerelease). `init_version()` is a standalone function that both reads and writes
`__version__ = "..."` in a package's `__init__.py` via regex, depending on whether `new_version` is
passed.

### `modfile.py` (untracked, in progress)
Helpers for writing Autodesk Maya `.mod` module descriptor files (`_write_mod_file`) so a
published package can register itself on `MAYA_MODULE_PATH`. Not wired up: `cli.py` carries a
commented-out `--write-mod` flag and a `writemod` subcommand stub referencing this module. If asked
to finish the feature, the intended shape is in those comments.

## Conventions

- Subcommand functions (`cmd_*`) take an `argparse.Namespace` and return an `int` exit code;
  `main()` does `int(args.func(args))`. Tests call `cmd_*` directly with a hand-built `Namespace`
  rather than going through `main()` and `sys.argv`.
- Every positional `root_dir` / `source_path` defaults to `.`: subcommands are meant to run from
  inside the target package, with the positional as an override.
- `CMD_FORMAT` in `cli.py` holds raw ANSI escape codes for coloured output; no colour library.
