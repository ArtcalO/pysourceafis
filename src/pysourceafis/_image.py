"""Turning user input (paths, bytes, Pillow images, numpy arrays) into 8-bit grayscale pixels."""

from __future__ import annotations

import io
import os
import warnings
from dataclasses import dataclass
from typing import Any

from .errors import ImageError

#: Largest accepted image, in pixels (decompression-bomb guard). 25 MP covers 1000 dpi rolled prints.
MAX_PIXELS = 25_000_000
#: Largest accepted encoded file, in bytes.
MAX_BYTES = 50 * 1024 * 1024
MIN_SIDE = 32


@dataclass(frozen=True)
class Gray:
    width: int
    height: int
    pixels: bytes  # row-major, 0 = black


def _from_pil(img) -> Gray:
    if getattr(img, "n_frames", 1) != 1:
        raise ImageError("Multi-frame images are not supported; pass a single frame.")
    w, h = img.size
    _check_size(w, h)
    gray = img.convert("L")
    return Gray(w, h, gray.tobytes())


def _check_size(w: int, h: int) -> None:
    if w < MIN_SIDE or h < MIN_SIDE:
        raise ImageError(f"Image is {w}x{h} px; fingerprints need at least {MIN_SIDE}x{MIN_SIDE} px.")
    if w * h > MAX_PIXELS:
        raise ImageError(f"Image is {w}x{h} px, larger than the {MAX_PIXELS:,} pixel limit.")


def from_bytes(data: bytes) -> Gray:
    from PIL import Image, UnidentifiedImageError

    if not data:
        raise ImageError("The image is empty.")
    if len(data) > MAX_BYTES:
        raise ImageError(f"The image file is larger than {MAX_BYTES // (1024 * 1024)} MB.")
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        try:
            with Image.open(io.BytesIO(data)) as img:
                _check_size(*img.size)  # before decoding pixel data
                img.load()
                return _from_pil(img)
        except ImageError:
            raise
        except UnidentifiedImageError:
            raise ImageError("Unrecognised image format (supported: PNG, JPEG, BMP, TIFF, GIF, WebP...).") from None
        except (Image.DecompressionBombError, Image.DecompressionBombWarning):
            raise ImageError(f"Image exceeds the {MAX_PIXELS:,} pixel limit.") from None
        except Exception as exc:
            raise ImageError(f"The image is corrupt or truncated ({type(exc).__name__}).") from None


def from_path(path: str | os.PathLike) -> Gray:
    try:
        size = os.path.getsize(path)
    except OSError as exc:
        raise ImageError(f"Cannot read image file {os.fspath(path)!r}: {exc.strerror}") from None
    if size > MAX_BYTES:
        raise ImageError(f"{os.fspath(path)!r} is larger than {MAX_BYTES // (1024 * 1024)} MB.")
    with open(path, "rb") as f:
        return from_bytes(f.read())


def from_array(array: Any) -> Gray:
    """2-D uint8 array (height x width) or 3-D RGB/RGBA array."""
    try:
        import numpy as np
    except ImportError:  # pragma: no cover - only reachable when numpy is missing
        raise ImageError("Passing arrays requires numpy (pip install numpy).") from None
    a = np.asarray(array)
    if a.ndim == 3 and a.shape[2] in (3, 4):
        from PIL import Image

        return _from_pil(Image.fromarray(a.astype(np.uint8)[:, :, :3], mode="RGB"))
    if a.ndim != 2:
        raise ImageError(f"Expected a 2-D grayscale array, got shape {a.shape}.")
    if a.dtype != np.uint8:
        if np.issubdtype(a.dtype, np.floating) and a.size and a.max() <= 1.0:
            a = a * 255.0  # floats in [0, 1]
        a = np.clip(a, 0, 255).astype(np.uint8)
    h, w = a.shape
    _check_size(w, h)
    return Gray(w, h, np.ascontiguousarray(a).tobytes())


def load(source: Any) -> Gray:
    """Dispatch on the input type."""
    if isinstance(source, (str, os.PathLike)):
        return from_path(source)
    if isinstance(source, (bytes, bytearray, memoryview)):
        return from_bytes(bytes(source))
    if hasattr(source, "getvalue") or hasattr(source, "read"):
        data = source.getvalue() if hasattr(source, "getvalue") else source.read()
        return from_bytes(data)
    try:
        from PIL import Image

        if isinstance(source, Image.Image):
            return _from_pil(source)
    except ImportError:  # pragma: no cover
        pass
    if hasattr(source, "__array__") or hasattr(source, "shape"):
        return from_array(source)
    raise ImageError(
        f"Unsupported image input of type {type(source).__name__}; pass a path, bytes, "
        "a file object, a Pillow image or a numpy array."
    )
