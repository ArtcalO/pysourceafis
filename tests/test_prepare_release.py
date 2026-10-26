import importlib.util
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parent.parent / "tools"


def load(name):
    spec = importlib.util.spec_from_file_location(name, TOOLS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


prepare = load("prepare_release")
notes = load("release_notes")

FIRST = """# Changelog

Intro text.

## [Unreleased]

### Added

- Feature A.
"""


def test_first_release():
    out = prepare.update_changelog(FIRST, "0.1.0", "2026-10-26")
    assert "## [Unreleased]\n\n## [0.1.0] - 2026-10-26\n\n### Added\n\n- Feature A.\n" in out
    assert out.rstrip().endswith(
        "[Unreleased]: https://github.com/ArtcalO/pysourceafis/compare/v0.1.0...HEAD\n"
        "[0.1.0]: https://github.com/ArtcalO/pysourceafis/releases/tag/v0.1.0"
    )
    # the release workflow can read the new section
    assert notes.section(out, "0.1.0") == "### Added\n\n- Feature A.\n"


def test_second_release_links_versions():
    first = prepare.update_changelog(FIRST, "0.1.0", "2026-10-26")
    second = first.replace("## [Unreleased]\n", "## [Unreleased]\n\n### Fixed\n\n- Bug B.\n", 1)
    out = prepare.update_changelog(second, "0.2.0", "2026-11-02")
    assert out.index("## [0.2.0]") < out.index("## [0.1.0]")
    assert "[0.2.0]: https://github.com/ArtcalO/pysourceafis/compare/v0.1.0...v0.2.0" in out
    assert "compare/v0.2.0...HEAD" in out and out.count("[0.1.0]: ") == 1
    assert notes.section(out, "0.2.0") == "### Fixed\n\n- Bug B.\n"


def test_refuses_empty_unreleased_and_duplicates():
    first = prepare.update_changelog(FIRST, "0.1.0", "2026-10-26")
    with pytest.raises(SystemExit, match="Nothing under"):
        prepare.update_changelog(first, "0.2.0", "2026-11-02")
    with pytest.raises(SystemExit, match="already has"):
        prepare.update_changelog(FIRST.replace("## [Unreleased]", "## [0.1.0] - x\n\n## [Unreleased]"), "0.1.0", "d")


def test_real_changelog_has_unreleased_notes():
    text = (TOOLS.parent / "CHANGELOG.md").read_text(encoding="utf-8")
    out = prepare.update_changelog(text, "9.9.9", "2026-01-01")  # dry run, nothing written
    assert "## [9.9.9] - 2026-01-01" in out and "Fingerprint" in notes.section(out, "9.9.9")
