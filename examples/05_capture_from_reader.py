"""
Capture from a USB fingerprint reader and identify the finger (Windows).

Run from a terminal opened with "Run as administrator" - Windows only releases
raw fingerprint images to elevated programs.

    python examples/05_capture_from_reader.py enroll alice
    python examples/05_capture_from_reader.py identify

Templates are kept in ./demo-templates/ (biometric data: delete it afterwards).
"""

import sys
from pathlib import Path

from pysourceafis import Fingerprint, Gallery
from pysourceafis.readers import Reader, ReaderError

STORE = Path("demo-templates")
THRESHOLD = 60.0


def capture() -> Fingerprint:
    reader = Reader()
    print(f"Place a finger on {reader.info.manufacturer} {reader.info.model}...")
    shot = reader.capture(timeout=30)
    fp = shot.fingerprint()
    print(f"captured {shot.width}x{shot.height} px, {fp.minutiae_count} minutiae")
    return fp


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ("enroll", "identify"):
        print(__doc__)
        return 2
    try:
        fp = capture()
    except ReaderError as exc:
        print(f"Reader problem: {exc}")
        return 1
    STORE.mkdir(exist_ok=True)
    if sys.argv[1] == "enroll":
        name = sys.argv[2] if len(sys.argv) > 2 else "someone"
        (STORE / f"{name}.template").write_bytes(fp.to_bytes())
        print(f"enrolled {name}")
        return 0
    with Gallery() as gallery:
        gallery.add_templates((p.stem, p.read_bytes()) for p in STORE.glob("*.template"))
        hit = gallery.identify(fp, THRESHOLD)
        print(f"identified: {hit.key} (score {hit.score:.1f})" if hit else "not identified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
