"""
Search a probe in a gallery (1:N identification) with synthetic fingerprints.

    python examples/02_gallery_search.py
"""

import time

from pysourceafis import Fingerprint, Gallery
from pysourceafis.testing import synthetic_image

PEOPLE = 50
THRESHOLD = 60.0  # higher than the 1:1 threshold: 1:N search needs it (see docs/guide.md)


def main():
    print(f"Enrolling {PEOPLE} SYNTHETIC people...")
    t0 = time.perf_counter()
    enrolled = [(f"person-{i:03d}", Fingerprint.from_bytes(synthetic_image(i, 0))) for i in range(PEOPLE)]
    print(f"  generated and extracted in {time.perf_counter() - t0:.1f} s (image generation is the slow part)")

    with Gallery() as gallery:
        gallery.add_many(enrolled)

        probe = Fingerprint.from_bytes(synthetic_image(17, 1))  # a new capture of person-017's finger
        for match in gallery.search(probe, top_k=3):
            print(f"  {match.key}: {match.score:.1f}")
        stats = gallery.last_search
        print(f"  compared {stats.comparisons} fingerprints in {stats.milliseconds:.0f} ms")

        hit = gallery.identify(probe, threshold=THRESHOLD)
        print(f"identified: {hit.key if hit else 'nobody'}")

        stranger = Fingerprint.from_bytes(synthetic_image(10_000, 0))  # never enrolled
        print(f"stranger identified as: {gallery.identify(stranger, threshold=THRESHOLD)}")


if __name__ == "__main__":
    main()
