# dlpkg tests

Tests use `pytest`. It is installed in the shared venv `D:\Dev\venvs\python313` but not in
`py -3.10` or `py -3.14`; run `pip install pytest` in whichever environment you test with.

## Running

```commandline
pytest                                          # all tests
pytest tests/test_versioning.py                 # one file
pytest tests/test_versioning.py::test_bump      # one test
```

`pyproject.toml`'s `[tool.pytest.ini_options]` sets `pythonpath = ["src"]` and
`testpaths = ["tests"]`, so no `PYTHONPATH` is needed. `src` goes first on the path on purpose:
the venv's editable install of dlpkg points at the main checkout, and without this a test run
inside a worktree would silently exercise the main checkout's code instead of the worktree's.

Shared fixtures (`temp_toml_package`, `published_versions_dir`) live in `tests/conftest.py` and
are auto-loaded; do not import them.

`test_cmd_build` is slow: it upgrades pip and build and runs a real build. Skip it while iterating
with `--deselect tests/test_cli.py::test_cmd_build`, and run the full suite once before committing.
