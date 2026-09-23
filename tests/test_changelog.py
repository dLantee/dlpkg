from datetime import date

import pytest

from dlpkg.changelog import release_changelog

SAMPLE = """# Changelog

## [Unreleased]

### Added
- New thing.

## [0.6.0] - 2026-09-22

### Fixed
- Old thing.


[Unreleased]: https://github.com/dLantee/dlpkg/compare/v0.6.0...HEAD
[0.6.0]: https://github.com/dLantee/dlpkg/compare/v0.5.2...v0.6.0
[#7]: https://github.com/dLantee/dlpkg/issues/7
"""


def test_release_moves_unreleased_into_dated_section():
    out = release_changelog(SAMPLE, "0.7.0", date(2026, 10, 1))
    assert "## [Unreleased]\n\n## [0.7.0] - 2026-10-01\n\n### Added\n- New thing.\n\n## [0.6.0] - 2026-09-22" in out
    assert out.count("- New thing.") == 1


def test_release_repoints_compare_links():
    out = release_changelog(SAMPLE, "0.7.0", date(2026, 10, 1))
    assert "[Unreleased]: https://github.com/dLantee/dlpkg/compare/v0.7.0...HEAD\n" in out
    assert "[0.7.0]: https://github.com/dLantee/dlpkg/compare/v0.6.0...v0.7.0\n" in out
    assert "[0.6.0]: https://github.com/dLantee/dlpkg/compare/v0.5.2...v0.6.0\n" in out
    assert out.index("[0.7.0]:") < out.index("[0.6.0]:")
    assert "[#7]: https://github.com/dLantee/dlpkg/issues/7" in out


def test_release_without_links_leaves_foot_alone():
    text = SAMPLE.split("\n\n[Unreleased]:")[0] + "\n"
    out = release_changelog(text, "0.7.0", date(2026, 10, 1))
    assert "## [0.7.0] - 2026-10-01" in out
    assert "compare" not in out


def test_release_with_unreleased_as_last_section():
    text = "# Changelog\n\n## [Unreleased]\n\n- First release.\n"
    out = release_changelog(text, "0.1.0", date(2026, 10, 1))
    assert out == "# Changelog\n\n## [Unreleased]\n\n## [0.1.0] - 2026-10-01\n\n- First release.\n"


def test_release_refuses_empty_unreleased():
    text = "# Changelog\n\n## [Unreleased]\n\n## [0.6.0] - 2026-09-22\n- x\n"
    with pytest.raises(ValueError, match="empty"):
        release_changelog(text, "0.7.0", date(2026, 10, 1))


def test_release_refuses_missing_unreleased():
    with pytest.raises(ValueError, match="Unreleased"):
        release_changelog("# Changelog\n\n## [0.6.0] - 2026-09-22\n- x\n", "0.7.0", date(2026, 10, 1))
