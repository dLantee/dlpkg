# dlpkg

## What this is

`dlpkg` is a Python CLI tool (installed as the `dlpkg` command via `[project.scripts]`) for
managing *other* Python packages' development lifecycle: `version` (read/bump semver), then
`build` (wheel via `python -m build`), then `publish` (copy into a versioned target dir via
`pip install --target`). It is not a build backend itself. It shells out to `pip` and `build` and
edits `pyproject.toml` / `__init__.py` directly.

## Technology 🔬

- Requires Python >=3.13.
- Runtime dependency: `tomlkit`. All TOML reading and writing must preserve
formatting and comments, so use `tomlkit`, never `tomllib` or `toml`.

There is no configured lint/typecheck command (no ruff/mypy config present).

## Where to look

- `.claude/structure.md`: module layout, what each file does, conventions.
- `.claude/testing.md`: how to run the tests, and which tests are known to be broken.
- `README.md`: How to use the tool and usage examples.
