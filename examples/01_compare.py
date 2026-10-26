"""
Compare two fingerprints (1:1 verification).

    python examples/01_compare.py                 # uses synthetic demo images
    python examples/01_compare.py a.png b.png     # your own images
"""

import sys

from pysourceafis import RECOMMENDED_THRESHOLD, Fingerprint


def load_pair():
    if len(sys.argv) == 3:
        return Fingerprint.from_file(sys.argv[1]), Fingerprint.from_file(sys.argv[2])
    from pysourceafis.testing import synthetic_image  # pip install "pysourceafis[testing]"

    print("No images given: using SYNTHETIC demo fingerprints (two captures of the same finger).")
    return Fingerprint.from_bytes(synthetic_image(1, 0)), Fingerprint.from_bytes(synthetic_image(1, 1))


def main():
    a, b = load_pair()
    print(f"minutiae: {a.minutiae_count} and {b.minutiae_count}")
    score = a.match(b)
    verdict = "same finger" if score >= RECOMMENDED_THRESHOLD else "different fingers"
    print(f"similarity score {score:.1f} -> {verdict} (threshold {RECOMMENDED_THRESHOLD})")


if __name__ == "__main__":
    main()
