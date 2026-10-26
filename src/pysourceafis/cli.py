"""
Command line interface.

    pysourceafis doctor                       check the installation
    pysourceafis compare a.png b.png          similarity score of two images
    pysourceafis extract finger.png -o t.bin  save a template
    pysourceafis identify probe.png gallery/  search a folder of images/templates
    pysourceafis version

Also available as ``python -m pysourceafis``.
"""
from __future__ import annotations

import argparse
import json
import platform
import sys
import time
from pathlib import Path

from ._version import __version__
from .errors import SourceAfisError

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".gif", ".webp"}
TEMPLATE_SUFFIXES = {".bin", ".cbor", ".template"}


def _load(path: Path, dpi: float):
    from .fingerprint import Fingerprint

    if path.suffix.lower() in TEMPLATE_SUFFIXES:
        return Fingerprint.from_template(path.read_bytes())
    return Fingerprint.from_file(path, dpi=dpi)


def cmd_doctor(args) -> int:
    from . import _java

    ok = True

    def line(status: str, label: str, detail: str = "") -> None:
        print(f"  [{status:^4}] {label}" + (f": {detail}" if detail else ""))

    print(f"pysourceafis {__version__} on Python {platform.python_version()} "
          f"({platform.system()} {platform.machine()})")
    try:
        import jpype

        line("ok", "JPype", jpype.__version__)
    except ImportError:
        line("FAIL", "JPype", "not installed -> pip install JPype1")
        return 1
    try:
        java = _java.find_java()
        line("ok", "Java", f"{java.version} from {java.source} ({java.home})")
    except SourceAfisError as exc:
        line("FAIL", "Java", str(exc))
        return 1
    try:
        jars = _java.jar_files()
        line("ok", "Engine jars", f"{len(jars)} jars in {_java.JARS_DIR}")
    except SourceAfisError as exc:
        line("FAIL", "Engine jars", str(exc))
        return 1
    try:
        from .fingerprint import engine_version

        t0 = time.perf_counter()
        version = engine_version()
        line("ok", "SourceAFIS", f"{version} (JVM started in {time.perf_counter() - t0:.1f} s)")
    except SourceAfisError as exc:
        line("FAIL", "SourceAFIS", str(exc))
        return 1
    try:
        from .fingerprint import Fingerprint
        from .testing import synthetic_image

        a = Fingerprint.from_bytes(synthetic_image(1, 0))
        b = Fingerprint.from_bytes(synthetic_image(1, 1))
        c = Fingerprint.from_bytes(synthetic_image(2, 0))
        genuine, impostor = a.match(b), a.match(c)
        good = genuine > impostor
        ok &= good
        line("ok" if good else "FAIL", "Self-test (synthetic images)",
             f"same finger {genuine:.1f}, different fingers {impostor:.1f}")
    except ImportError:
        line("skip", "Self-test", "needs numpy (pip install 'pysourceafis[testing]')")
    print("Everything looks good." if ok else "Some checks failed - see above.")
    return 0 if ok else 1


def cmd_compare(args) -> int:
    a, b = _load(Path(args.a), args.dpi), _load(Path(args.b), args.dpi)
    score = a.match(b)
    if args.json:
        print(json.dumps({"score": score, "threshold": args.threshold, "match": score >= args.threshold}))
    else:
        verdict = "MATCH" if score >= args.threshold else "no match"
        print(f"{score:.2f}  ({verdict} at threshold {args.threshold})")
    return 0


def cmd_extract(args) -> int:
    from .fingerprint import Fingerprint

    fp = Fingerprint.from_file(args.image, dpi=args.dpi)
    out = Path(args.output) if args.output else Path(args.image).with_suffix(".template")
    out.write_bytes(fp.to_bytes())
    print(f"{out}  ({fp.minutiae_count} minutiae, {len(fp.to_bytes())} bytes). Templates are biometric data.")
    return 0


def cmd_identify(args) -> int:
    from .gallery import Gallery

    folder = Path(args.gallery)
    files = sorted(p for p in folder.rglob("*") if p.suffix.lower() in IMAGE_SUFFIXES | TEMPLATE_SUFFIXES)
    if not files:
        print(f"No images or templates found in {folder}", file=sys.stderr)
        return 2
    probe = _load(Path(args.probe), args.dpi)
    with Gallery() as gallery:
        skipped = 0
        for p in files:
            try:
                gallery.add(str(p.relative_to(folder)), _load(p, args.dpi))
            except SourceAfisError as exc:
                skipped += 1
                print(f"skip {p}: {exc}", file=sys.stderr)
        hits = gallery.search(probe, top_k=args.top_k)
        stats = gallery.last_search
    if args.json:
        print(json.dumps({"threshold": args.threshold, "candidates": [
            {"key": h.key, "score": h.score, "match": h.score >= args.threshold} for h in hits]}))
        return 0
    print(f"Searched {stats.comparisons} fingerprints in {stats.milliseconds:.0f} ms"
          + (f" ({skipped} skipped)" if skipped else ""))
    for rank, h in enumerate(hits, 1):
        mark = "MATCH" if h.score >= args.threshold else ""
        print(f"{rank:3d}. {h.score:8.2f}  {h.key}  {mark}")
    return 0


def main(argv: list[str] | None = None) -> int:
    from .fingerprint import DEFAULT_DPI, RECOMMENDED_THRESHOLD

    ap = argparse.ArgumentParser(prog="pysourceafis", description="Fingerprint matching powered by SourceAFIS.")
    sub = ap.add_subparsers(dest="command", required=True)

    def common(p, threshold=False):
        p.add_argument("--dpi", type=float, default=DEFAULT_DPI, help="image resolution (default 500)")
        if threshold:
            p.add_argument("--threshold", type=float, default=RECOMMENDED_THRESHOLD,
                           help=f"match threshold (default {RECOMMENDED_THRESHOLD}; calibrate for your data)")
            p.add_argument("--json", action="store_true", help="machine-readable output")

    sub.add_parser("doctor", help="check Java, the engine and run a self-test").set_defaults(func=cmd_doctor)
    sub.add_parser("version", help="print versions").set_defaults(func=lambda a: print_version())
    p = sub.add_parser("compare", help="similarity score of two images or templates")
    p.add_argument("a")
    p.add_argument("b")
    common(p, threshold=True)
    p.set_defaults(func=cmd_compare)
    p = sub.add_parser("extract", help="save the template of an image")
    p.add_argument("image")
    p.add_argument("-o", "--output")
    common(p)
    p.set_defaults(func=cmd_extract)
    p = sub.add_parser("identify", help="search a probe in a folder of images/templates")
    p.add_argument("probe")
    p.add_argument("gallery")
    p.add_argument("--top-k", type=int, default=5)
    common(p, threshold=True)
    p.set_defaults(func=cmd_identify)

    args = ap.parse_args(argv)
    try:
        return int(args.func(args) or 0)
    except SourceAfisError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def print_version() -> int:
    from .fingerprint import engine_version

    print(f"pysourceafis {__version__}, SourceAFIS {engine_version()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
