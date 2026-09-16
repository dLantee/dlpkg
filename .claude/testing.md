# dlpkg tests

Tests use `pytest`. It is installed in the active venv (`D:\Dev\venvs\python313`) but not in
`py -3.10` or `py -3.14`; run `pip install pytest` in whichever environment you test with. There is
no `pytest.ini`, `tox.ini` or dev-requirements file; pytest config is entirely default.

## Running

Tests import shared fixtures with a bare `from fixtures import temp_toml_package`, not a relative
import. `tests/__init__.py` exists (empty) so `tests/` is a package, which makes pytest's default
`prepend` import mode add the repo root to `sys.path`, not `tests/`. A plain `pytest` therefore
fails with `ModuleNotFoundError: No module named 'fixtures'`. Put `tests/` on `PYTHONPATH`:

```commandline
PYTHONPATH=tests pytest                                        # all tests (bash / git-bash)
PYTHONPATH=tests pytest tests/test_versioning.py               # one file
PYTHONPATH=tests pytest tests/test_versioning.py::test_bump    # one test
```

On PowerShell: `$env:PYTHONPATH = "tests"; pytest`.

Do not add relative imports to `fixtures`; that breaks under this setup too.

## Known-broken tests

Pre-existing, verified via `git stash`. They are not a spec for current behaviour.

- `tests/test_publisher.py` imports `from dlpkg.publisher import publish_folder`, but
  `publisher.py` was deleted in the 0.3.0 refactor (its logic moved into `cli.py`'s
  `cmd_publish`). Fails on collection.
- `test_publish_basic` (`test_cli.py`) builds its `argparse.Namespace` with `root_dir=...`, but
  `cmd_publish` reads `args.source_path`. Fails with `AttributeError`.
- `test_update_args_from_files_publish_out_dir_uses_config_publish_dir`,
  `..._falls_back_to_maya_module_path` and `..._raises_if_no_config_and_no_env` (`test_cli.py`)
  reference `cli._get_pyproject_doc`, `cli._get_config_doc` and `cli._update_args_from_files`,
  none of which exist in current `cli.py`. Fail with `AttributeError`.
