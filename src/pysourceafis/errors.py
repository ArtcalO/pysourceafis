"""Exceptions raised by pysourceafis. Every message says what to do next."""
from __future__ import annotations


class SourceAfisError(Exception):
    """Base class for all pysourceafis errors."""


class JavaNotFoundError(SourceAfisError):
    """No usable Java runtime (11 or newer) was found."""


class EngineError(SourceAfisError):
    """The SourceAFIS engine could not be started or failed unexpectedly."""


class ImageError(SourceAfisError, ValueError):
    """The input is not a usable fingerprint image."""


class TemplateError(SourceAfisError, ValueError):
    """Serialized template bytes are invalid or come from an incompatible engine version."""
