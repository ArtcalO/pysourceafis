"""Shared fixtures. All fingerprints in the test suite are SYNTHETIC (pysourceafis.testing)."""

from __future__ import annotations

import functools

import pytest

from pysourceafis import Fingerprint
from pysourceafis.testing import synthetic_image


@functools.cache
def png(finger: int, impression: int = 0) -> bytes:
    return synthetic_image(finger, impression)


@functools.cache
def fp(finger: int, impression: int = 0) -> Fingerprint:
    return Fingerprint.from_bytes(png(finger, impression))


@pytest.fixture
def make_fp():
    return fp


@pytest.fixture
def make_png():
    return png
