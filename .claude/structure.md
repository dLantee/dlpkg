# dlpkg structure

```
src/dlpkg/
    cli.py          argparse tree plus every cmd_* subcommand; no dispatch layer
    package.py      PythonPackage facade: name, version, authors, source dirs
    tomlutil.py     TomlFile base, PyProjectToml, ConfigToml (tomlkit)
    versioning.py   SemVer dataclass and init_version() for __init__.py
    util.py         subprocess and filesystem helpers
    modfile.py      untracked, in-progress Maya .mod writer
tests/              pytest suite, see .claude/testing.md
config.toml         persisted defaults, read by ConfigToml
```

## Key behaviour

- `cmd_publish` takes a package root or a `.whl` path. From a wheel it parses name and version out of
  the filename.
- Output folder precedence: CLI flag, then `DLPKG_PUBLISH_DIR`, then `ConfigToml.publish_dir`.
  `cmd_publish` falls back to `./publish`; `cmd_list` raises instead.
- `cmd_list` scans `<dir>/<name>/rel-*` and `dev-*`, sorts with `SemVer`, and shows each folder's
  creation time as the publish timestamp. No metadata file is written.
- `cmd_config get|set|list` is the only supported way to persist settings in `config.toml`.
- `cmd_build --out-dir` is still hardcoded to `./build`, not wired to `ConfigToml.build_dir`.
- `PythonPackage` reads the version from `pyproject.toml` first, then `__version__` in `__init__.py`.
  Setting it writes both when both exist.
- `PyProjectToml.source_roots` finds the source dir the way setuptools does, so `--source-dir` is
  rarely needed.
- `modfile.py` is not wired up. `cli.py` keeps a commented-out `--write-mod` flag and `writemod`
  subcommand stub showing the intended shape.

## Conventions

- `cmd_*` functions take an `argparse.Namespace` and return an `int` exit code. Tests call them
  directly with a hand-built `Namespace`.
- Positional `root_dir` / `source_path` defaults to `.`, so commands run from inside the target package.
- `CMD_FORMAT` in `cli.py` holds raw ANSI codes; no colour library.
