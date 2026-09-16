# dlpkg

## Overrides

- Tests use `pytest` (overrides the `tools/` default of `unittest`). See `.claude/testing.md`.

## What this is

`dlpkg` is a Python CLI tool (installed as the `dlpkg` command via `[project.scripts]`) for
managing *other* Python packages' development lifecycle: `version` (read/bump semver), then
`build` (wheel via `python -m build`), then `publish` (copy into a versioned target dir via
`pip install --target`). It is not a build backend itself. It shells out to `pip` and `build` and
edits `pyproject.toml` / `__init__.py` directly.

Requires Python >=3.13. Runtime dependency: `tomlkit`. All TOML reading and writing must preserve
formatting and comments, so use `tomlkit`, never `tomllib` or `toml`.

## Common commands

```commandline
py -m pip install -e .           # install dlpkg locally for development (editable)
dlpkg version [root_dir]         # print current version
dlpkg version --bump patch       # bump patch/minor/major/prerelease
dlpkg build --out-dir DIR        # build wheel+sdist via `python -m build`
dlpkg publish --out-dir DIR      # publish into DIR/<name>/<channel>-<version>/ (or config.toml's
                                 # publish_dir / DLPKG_PUBLISH_DIR if --out-dir is omitted; falls
                                 # back to ./publish if none of those are set)
dlpkg list <name> --dir DIR      # list published rel-*/dev-* versions under DIR/<name>/, with
                                 # each version's publish timestamp
dlpkg config set publish_dir DIR # persist a default publish/list folder in config.toml
```

There is no configured lint/typecheck command (no ruff/mypy config present).

## Where to look

- `.claude/structure.md`: module layout, what each file does, conventions.
- `.claude/testing.md`: how to run the tests, and which tests are known to be broken.
- `.claude/git-workflow.md`: where dlpkg's own version is copied, release test command.
