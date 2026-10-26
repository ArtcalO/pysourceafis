"""
SYNTHETIC fingerprint-like images for tests, examples and bug reports.

They are generated from random parameters, belong to nobody and must never be
presented as real biometric data or used to claim accuracy on real
fingerprints. Requires numpy (``pip install "pysourceafis[testing]"``).

    >>> from pysourceafis.testing import synthetic_image
    >>> png = synthetic_image(finger=7, impression=0)          # PNG bytes  # doctest: +SKIP
    >>> other = synthetic_image(finger=7, impression=1)        # same finger, new impression  # doctest: +SKIP
"""

from __future__ import annotations

from .synthetic import HEIGHT, WIDTH, SyntheticFinger, make_finger, render_impression


def synthetic_array(finger: int, impression: int = 0, variation: float = 1.0):
    """(400, 320) uint8 numpy array of a synthetic impression (dark ridges, 500 dpi)."""
    return render_impression(make_finger(finger), impression, variation)


def synthetic_image(finger: int, impression: int = 0, variation: float = 1.0, format: str = "PNG") -> bytes:
    """Encoded synthetic impression. Same ``finger`` + different ``impression`` = a genuine pair."""
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.fromarray(synthetic_array(finger, impression, variation), mode="L").save(buf, format=format)
    return buf.getvalue()


__all__ = [
    "HEIGHT",
    "WIDTH",
    "SyntheticFinger",
    "make_finger",
    "render_impression",
    "synthetic_array",
    "synthetic_image",
]
