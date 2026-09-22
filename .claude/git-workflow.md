# Git workflow: dlpkg deltas

Everything not listed here follows `D:\Dev\.claude\git-workflow.md`.

## Version copies

`pyproject.toml` `[project].version` is the source of truth, written as a literal.

Copies that must agree with it:

- `src/dlpkg/__init__.py`: `__version__ = "x.y.z"`.
- `CHANGELOG.md`: the newest `## [x.y.z]` heading.

`README.md` quotes no version string.

dlpkg bumps itself: `dlpkg version --bump <patch|minor|major>` run in the repo root updates
`pyproject.toml` and `__init__.py` together, because `PythonPackage` writes to both when both exist.

## Test command

```
pytest
```

from the repo root. See `.claude/testing.md` for details and the slow test to skip while iterating.
