# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- `dlpkg publish` writes a `dlpkg.toml` metadata file into every published version folder with
  the package name, channel, version, publish time and git commit.
- `dlpkg publish --write-mod` writes a Maya `<name>.mod` pointing at the published folder into
  the new `mod_dir` config setting, or the first existing folder on `MAYA_MODULE_PATH`.
- `dlpkg use <name> <channel>-<version>` points the Maya `.mod` file at an already published
  version, to switch between dev and rel builds or roll back without republishing.
- `dlpkg list` marks the version the Maya `.mod` file currently points at with `(active)`.
- `dlpkg publish --channel dev` from a git checkout appends the short commit hash as SemVer build
  metadata (`dev-1.2.5+abc1234`), so dev publishes from different commits never collide.
- `dlpkg prune <name> [--channel dev] [--keep 3] [--dry-run]` deletes old published versions of
  one channel, keeping the newest ones and never the version the Maya `.mod` file points at.
- `dlpkg release --bump <major|minor|patch> [--dry-run]` bumps the version, moves the changelog's
  Unreleased entries under a dated heading with a compare link, commits `Release vX.Y.Z` and tags
  it. It refuses a dirty working tree or an empty Unreleased section, and never pushes.

### Changed
- `dlpkg list` reads each version's timestamp from `dlpkg.toml`, falling back to the folder's
  creation time for versions published before this change.
- `dlpkg build` honours the `build_dir` config setting when `--out-dir` is not passed
  (`--out-dir` > `build_dir` > `./build`). The shipped `config.toml` no longer sets `build_dir`,
  since a relative value there resolves against the dlpkg repo, not the package being built.
- README describes the current flags and commands; the stale `--version` and `--write-mod`
  descriptions and the claim that `publish` builds first are gone.
- Internal: the published-store scanning moved from `cli.py` into a new `published.py` module.

## [0.6.0] - 2026-09-22

### Changed
- `pytest` runs without `PYTHONPATH`: `pyproject.toml` puts `src` on the path and the shared
  fixtures moved to `tests/conftest.py`.
- Internal cleanup: `init_version` split into `read_init_version` and `write_init_version`,
  `dlpkg publish` and `dlpkg list` share one publish-dir lookup, `_scan_published_versions`
  returns a dict keyed by channel, defaults and names are module constants, dead code and
  commented-out experiments removed.

### Fixed
- `dlpkg version --bump` no longer fails when the source tree has no `__init__.py` or no
  `__version__` in it; `pyproject.toml` is updated and the `__init__.py` write is best effort.
- `SemVer` hashing now ignores build metadata, matching its equality.
- Broken tests that targeted removed code were fixed or deleted; the suite is green.

### Removed
- Unused helpers `copytree`, `is_git_repo`, `get_source_root`, `get_pyproject_root` and the
  `verbose` flag of `init_version`.

## [0.5.2] - 2026-07-15

### Fixed
- `dlpkg publish` now respects `config.toml`'s `publish_dir` when `--out-dir` isn't passed
  (previously `--out-dir` always defaulted to the hardcoded `./publish`, so the configured
  `publish_dir` was silently ignored). Resolution now follows `--out-dir` > `DLPKG_PUBLISH_DIR`
  env var > `config.toml publish_dir` > `./publish`, matching `dlpkg list`'s existing precedence.

## [0.5.1] - 2026-07-15
- Clean git history

## [0.5.0] - 2026-07-15

### Added
- Added `config` sub-command (`dlpkg config get|set|list`) for viewing and setting
  `config.toml` values, git-config style.
- Added `--limit` flag and a `list_limit` config setting to control how many `rel-`/`dev-`
  versions `dlpkg list` shows (previously hardcoded to 10).
- `dlpkg list` now shows each version's publish timestamp (read from the version folder's
  filesystem creation time) alongside its version number.

### Changed
- Renamed `install_dir` to `publish_dir` in `config.toml`'s `[defaults]` table (and
  `ConfigToml.install_dir` → `ConfigToml.publish_dir`) for consistency with the `publish`
  sub-command.
- Removed `list --set-default-dir`; use `dlpkg config set publish_dir PATH` instead.

## [0.4.0] - 2026-07-14

### Added
- Added `list` sub-command to display published versions of a package.

### Changed
- Renamed `default_paths.toml` to `config.toml` and fixed `ConfigToml`'s stale key names
  (`distribution_dir`/`publish_dir`) to match the file's actual keys (`build_dir`/`install_dir`).
  `dlpkg list` now reads/writes `install_dir` as its default folder.
- Renamed `install` sub-command to `publish` for clarity.

## [0.3.3] - 2026-07-14

### Added
- Show version and install location on dlpkg --help

## [0.3.2] - 2026-07-14

### Changed
- Bump minimum supported Python version to 3.13 ([#15])

## [0.3.1] - 2026-02-25

### Fixed
- Fixed an issue where the `version` command did version bumping but still throw error.
- Fixed a wrong argument call from parser in `cmd_build`.

### Added
- Added installing from wheel file in `install` sub-command.

## [0.3.0] - 2026-02-25

### Added
- Added new tests for all modules.

### Changed
- `version` sub-command now handles both printing the current version and bumping the version. ([#7])
- Removed `bump` sub-command. Version bumping is now handled by `version --bump PART`. ([#7])
- Renamed `publish` sub-command to `install` for clarity. ([#7])
- Each sub-commands without position arguments will now default to operating on the current working directory.
- Renamed default key from `publish_dir` to `install_dir` in `default_paths.toml`. ([#10])
- Renamed `dist_dir` to `build_dir` in `default_paths.toml`. ([#10])
- Renamed `dist` folder to `build` as default output folder for build command. ([#10])

### Updated
- Updated `README` to reflect the new command structure and usage.
- Deleted `builder.py` and `publisher.py` modules. Their functionality has been moved to CLI module.

## [0.2.0] - 2026-02-14

### Added
- Added `version` sub-command to print the current version of the package.
- Added `version --bump PART` to bump the version.
- Added `build` sub-command to build the package.
- Added `install` sub-command to install the package.

### Updated
- README with usage instructions for the new `version` command.

## [0.1.0] - 2026-02-04

- Initial release of dlpkg.


[Unreleased]: https://github.com/dLantee/dlpkg/compare/v0.6.0...HEAD
[0.6.0]: https://github.com/dLantee/dlpkg/compare/v0.5.2...v0.6.0
[#7]: https://github.com/dLantee/dlpkg/issues/7
[#10]: https://github.com/dLantee/dlpkg/issues/10
[#15]: https://github.com/dLantee/dlpkg/issues/15