#!/usr/bin/env python3
"""
Print the release notes of one version from CHANGELOG.md (used by the release workflow).

    python tools/release_notes.py 0.1.0          # notes for 0.1.0
    python tools/release_notes.py --check 0.1.0  # also verify _version.py matches

Exits with an error if the version has no section, so a release cannot be
published without release notes.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def section(changelog: str, version: str) -> str:
    pattern = re.compile(rf"^## \[{re.escape(version)}\][^\n]*\n(.*?)(?=^## \[|^\[[^\]]+\]: |\Z)", re.M | re.S)
    match = pattern.search(changelog)
    if not match or not match.group(1).strip():
        raise SystemExit(f"CHANGELOG.md has no (non-empty) section for version {version}.")
    return match.group(1).strip() + "\n"


def package_version() -> str:
    text = (ROOT / "src" / "pysourceafis" / "_version.py").read_text(encoding="utf-8")
    return re.search(r'__version__\s*=\s*"([^"]+)"', text).group(1)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("version", help="version without the leading v, e.g. 0.1.0")
    ap.add_argument("--check", action="store_true", help="fail if src/pysourceafis/_version.py differs")
    args = ap.parse_args()
    version = args.version.removeprefix("v")
    if args.check and package_version() != version:
        raise SystemExit(f"Tag says {version} but _version.py says {package_version()}.")
    sys.stdout.write(section((ROOT / "CHANGELOG.md").read_text(encoding="utf-8"), version))
    return 0


if __name__ == "__main__":
    sys.exit(main())
