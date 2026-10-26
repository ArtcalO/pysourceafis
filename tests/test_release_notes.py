import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "release_notes", Path(__file__).resolve().parent.parent / "tools" / "release_notes.py"
)
release_notes = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release_notes)

CHANGELOG = """# Changelog

## [Unreleased]

### Added
- Something new.

## [0.2.0] - 2026-11-01

### Fixed
- A bug.

## [0.1.0] - 2026-10-26

### Added
- First release.

[0.2.0]: https://example.org/compare/v0.1.0...v0.2.0
"""


def test_extracts_one_section():
    notes = release_notes.section(CHANGELOG, "0.2.0")
    assert notes == "### Fixed\n- A bug.\n"
    assert release_notes.section(CHANGELOG, "0.1.0") == "### Added\n- First release.\n"


def test_missing_version_fails():
    with pytest.raises(SystemExit, match="no \\(non-empty\\) section"):
        release_notes.section(CHANGELOG, "9.9.9")


def test_package_version_is_readable():
    assert release_notes.package_version().count(".") >= 2
