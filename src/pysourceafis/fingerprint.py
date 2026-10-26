"""Fingerprint templates and 1:1 matching."""
from __future__ import annotations

import os
from typing import Any

from . import _image, _java
from .errors import EngineError, ImageError, TemplateError

#: Starting point for a match decision recommended by SourceAFIS: score >= 40
#: roughly corresponds to a false match rate of 0.01% in 1:1 comparisons.
#: Calibrate on your own data, and use a higher threshold for 1:N search.
RECOMMENDED_THRESHOLD = 40.0

#: Default image resolution. SourceAFIS is tuned for 500 dpi scanners.
DEFAULT_DPI = 500.0

_classes: dict[str, Any] = {}


def _cls(name: str):
    jpype = _java.ensure_started()
    if name not in _classes:
        _classes[name] = jpype.JClass(name)
    return _classes[name]


def _bridge():
    return _cls("io.github.pysourceafis.Bridge")


def engine_version() -> str:
    """Version of the bundled SourceAFIS engine, e.g. ``"3.18.1"``."""
    return str(_bridge().sourceafisVersion())


def _check_dpi(dpi: float) -> float:
    dpi = float(dpi)
    if not 50 <= dpi <= 5000:
        raise ValueError(f"dpi={dpi} is out of range (50-5000); fingerprint scanners are usually 500 dpi.")
    return dpi


class Fingerprint:
    """
    A fingerprint template: the minutiae extracted from one image.

    Create one with :meth:`from_file`, :meth:`from_image` or :meth:`from_bytes`
    (feature extraction runs once), or restore a stored template with
    :meth:`from_template`. Templates are immutable and thread-safe.

    Templates are biometric data. Store them encrypted and do not log them.
    """

    __slots__ = ("_jt", "_data")

    def __init__(self, _java_template, _serialized: bytes | None = None):
        # Use the factory class methods; this constructor is internal.
        self._jt = _java_template
        self._data = _serialized

    # ------------------------------------------------------------ factories
    @classmethod
    def from_file(cls, path: str | os.PathLike, dpi: float = DEFAULT_DPI) -> Fingerprint:
        """Extract a template from an image file (PNG, JPEG, BMP, TIFF, ...)."""
        return cls._extract(_image.from_path(path), dpi)

    @classmethod
    def from_image(cls, image: Any, dpi: float = DEFAULT_DPI) -> Fingerprint:
        """Extract a template from a path, encoded bytes, file object, Pillow image or numpy array."""
        return cls._extract(_image.load(image), dpi)

    @classmethod
    def from_bytes(cls, image_bytes: bytes, dpi: float = DEFAULT_DPI) -> Fingerprint:
        """Extract a template from encoded image bytes (e.g. an uploaded PNG)."""
        return cls._extract(_image.from_bytes(image_bytes), dpi)

    @classmethod
    def from_pixels(cls, width: int, height: int, pixels: bytes, dpi: float = DEFAULT_DPI) -> Fingerprint:
        """Extract a template from raw 8-bit grayscale pixels, row by row, 0 = black."""
        if width * height != len(pixels):
            raise ImageError(f"Expected {width * height} bytes for {width}x{height} pixels, got {len(pixels)}.")
        return cls._extract(_image.Gray(width, height, bytes(pixels)), dpi)

    @classmethod
    def from_template(cls, data: bytes) -> Fingerprint:
        """Restore a template previously saved with :meth:`to_bytes`."""
        if not isinstance(data, (bytes, bytearray, memoryview)) or not data:
            raise TemplateError("Template data must be non-empty bytes.")
        data = bytes(data)
        jpype = _java.ensure_started()
        bridge = _bridge()
        recorded = str(bridge.templateVersion(jpype.JArray(jpype.JByte)(data)))
        try:
            jt = _cls("com.machinezoo.sourceafis.FingerprintTemplate")(jpype.JArray(jpype.JByte)(data))
        except jpype.JException as exc:
            raise TemplateError(f"Not a valid SourceAFIS template ({exc.getMessage()}).") from None
        current = engine_version()
        if recorded and not recorded.startswith(current):
            raise TemplateError(
                f"Template was created by SourceAFIS {recorded}, this is {current}. SourceAFIS templates are not "
                "compatible across versions: extract it again from the original image."
            )
        return cls(jt, data)

    @classmethod
    def _extract(cls, gray: _image.Gray, dpi: float) -> Fingerprint:
        jpype = _java.ensure_started()
        try:
            jt = _bridge().extract(gray.width, gray.height, jpype.JArray(jpype.JByte)(gray.pixels), _check_dpi(dpi))
        except jpype.JException as exc:
            raise EngineError(f"SourceAFIS could not process the image: {exc.getMessage()}") from None
        return cls(jt)

    # ---------------------------------------------------------- properties
    def to_bytes(self) -> bytes:
        """Serialize the template (SourceAFIS CBOR format) for storage."""
        if self._data is None:
            self._data = bytes(self._jt.toByteArray())
        return self._data

    @property
    def minutiae_count(self) -> int:
        """Number of minutiae (ridge endings and bifurcations). Very low counts mean a poor image."""
        jpype = _java.ensure_started()
        return int(_bridge().minutiaeCount(jpype.JArray(jpype.JByte)(self.to_bytes())))

    @property
    def memory_bytes(self) -> int:
        """In-memory size estimate of the deserialized template, as reported by SourceAFIS."""
        return int(self._jt.memory())

    # ------------------------------------------------------------- matching
    def match(self, other: Fingerprint) -> float:
        """
        Similarity score between this fingerprint and ``other`` (higher = more similar).

        The score is **not** a probability. Compare it to a threshold that you
        calibrated (see :data:`RECOMMENDED_THRESHOLD`). To compare one probe with
        many candidates, use :class:`Matcher` or :class:`~pysourceafis.Gallery`.
        """
        return Matcher(self).match(other)

    def __repr__(self) -> str:
        return f"<Fingerprint minutiae={self.minutiae_count}>"

    def __reduce__(self):
        # Pickling stores the serialized template (useful for multiprocessing).
        return (Fingerprint.from_template, (self.to_bytes(),))


class Matcher:
    """
    A probe prepared for fast repeated comparisons (1:N).

    Building the matcher costs some time and memory; reuse it for many
    candidates. :meth:`match` is thread-safe.
    """

    __slots__ = ("probe", "_jm")

    def __init__(self, probe: Fingerprint):
        if not isinstance(probe, Fingerprint):
            raise TypeError("Matcher expects a Fingerprint.")
        self.probe = probe
        self._jm = _cls("com.machinezoo.sourceafis.FingerprintMatcher")(probe._jt)

    def match(self, candidate: Fingerprint) -> float:
        """Similarity score between the probe and ``candidate``."""
        if not isinstance(candidate, Fingerprint):
            raise TypeError("match() expects a Fingerprint.")
        return float(self._jm.match(candidate._jt))
