#!/usr/bin/env python3
"""
Prepare a release commit: date the release notes and bump the version.

    python tools/prepare_release.py 0.1.0            # today's date
    python tools/prepare_release.py 0.2.0 --date 2026-12-01

What it does:
1. moves everything under "## [Unreleased]" in CHANGELOG.md into a new
   "## [X.Y.Z] - YYYY-MM-DD" section and leaves an empty [Unreleased] section;
2. rewrites the comparison links at the bottom of CHANGELOG.md;
3. sets __version__ in src/pysourceafis/_version.py.

Then review the diff, commit ("Release X.Y.Z"), tag vX.Y.Z and push the tag;
the release workflow publishes to PyPI and creates the GitHub release.
"""

from __future__ import annotations

import argparse
import datetime as dt
import itertools
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO_URL = "https://github.com/ArtcalO/pysourceafis"
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+(?:(?:a|b|rc)\d+)?$")


def released_versions(changelog: str) -> list[str]:
    return re.findall(r"^## \[(\d+\.\d+\.\d+(?:(?:a|b|rc)\d+)?)\]", changelog, re.M)


def update_changelog(changelog: str, version: str, date: str) -> str:
    if version in released_versions(changelog):
        raise SystemExit(f"CHANGELOG.md already has a section for {version}.")
    match = re.search(r"^## \[Unreleased\][^\n]*\n(.*?)(?=^## \[|^\[[^\]]+\]: |\Z)", changelog, re.M | re.S)
    if not match or not match.group(1).strip():
        raise SystemExit("Nothing under [Unreleased] - add release notes before releasing.")
    notes = match.group(1).strip()
    new_block = f"## [Unreleased]\n\n## [{version}] - {date}\n\n{notes}\n\n"
    changelog = changelog[: match.start()] + new_block + changelog[match.end() :]

    # Rebuild the link references at the end of the file.
    changelog = re.sub(r"(?m)^\[[^\]]+\]: \S+\n?", "", changelog).rstrip() + "\n\n"
    versions = released_versions(changelog)  # newest first
    links = [f"[Unreleased]: {REPO_URL}/compare/v{versions[0]}...HEAD"]
    for newer, older in itertools.pairwise(versions):
        links.append(f"[{newer}]: {REPO_URL}/compare/v{older}...v{newer}")
    links.append(f"[{versions[-1]}]: {REPO_URL}/releases/tag/v{versions[-1]}")
    return changelog + "\n".join(links) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("version")
    ap.add_argument("--date", default=dt.date.today().isoformat())
    args = ap.parse_args()
    version = args.version.removeprefix("v")
    if not VERSION_RE.match(version):
        raise SystemExit(f"{version!r} is not a version like 1.2.3 (or 1.2.3rc1).")
    dt.date.fromisoformat(args.date)

    changelog_path = ROOT / "CHANGELOG.md"
    changelog_path.write_text(
        update_changelog(changelog_path.read_text(encoding="utf-8"), version, args.date), encoding="utf-8"
    )
    version_path = ROOT / "src" / "pysourceafis" / "_version.py"
    version_path.write_text(f'__version__ = "{version}"\n', encoding="utf-8")
    print(f"Prepared {version} ({args.date}). Next:")
    print(f'  git commit -am "Release {version}" && git tag v{version} && git push origin main v{version}')
    return 0


if __name__ == "__main__":
    sys.exit(main())
