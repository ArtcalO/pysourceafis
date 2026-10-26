"""
pysourceafis - fingerprint matching for Python, powered by SourceAFIS.

    >>> from pysourceafis import Fingerprint, Gallery
    >>> a = Fingerprint.from_file("a.png")        # doctest: +SKIP
    >>> a.match(Fingerprint.from_file("b.png"))   # doctest: +SKIP
    183.2

Unofficial community wrapper around SourceAFIS for Java
(https://sourceafis.machinezoo.com/). Scores are similarity scores, not
probabilities.
"""
from ._version import __version__
from .errors import EngineError, ImageError, JavaNotFoundError, SourceAfisError, TemplateError
from .fingerprint import DEFAULT_DPI, RECOMMENDED_THRESHOLD, Fingerprint, Matcher, engine_version
from .gallery import Gallery, Match, SearchStats

__all__ = [
    "__version__",
    "DEFAULT_DPI",
    "RECOMMENDED_THRESHOLD",
    "EngineError",
    "Fingerprint",
    "Gallery",
    "ImageError",
    "JavaNotFoundError",
    "Match",
    "Matcher",
    "SearchStats",
    "SourceAfisError",
    "TemplateError",
    "engine_version",
]
