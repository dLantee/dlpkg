# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

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


[#7]: https://github.com/dLantee/dlpkg/issues/7
[#10]: https://github.com/dLantee/dlpkg/issues/10
[#15]: https://github.com/dLantee/dlpkg/issues/15