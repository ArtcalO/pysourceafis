import io
import struct
import zlib

import numpy as np
import pytest
from PIL import Image

from pysourceafis import ImageError, _image
from pysourceafis.testing import synthetic_array, synthetic_image


def encode(img: Image.Image, fmt: str) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


@pytest.mark.parametrize("fmt", ["PNG", "JPEG", "BMP", "TIFF"])
def test_formats(fmt):
    g = _image.from_bytes(synthetic_image(3, 0, format=fmt))
    assert (g.width, g.height) == (320, 400) and len(g.pixels) == 320 * 400


def test_all_input_types_agree(tmp_path):
    data = synthetic_image(3)
    path = tmp_path / "f.png"
    path.write_bytes(data)
    pil = Image.open(io.BytesIO(data))
    arr = np.asarray(pil)
    results = {_image.load(x).pixels for x in (str(path), path, data, bytearray(data), io.BytesIO(data), pil, arr)}
    assert len(results) == 1


def test_rgb_and_float_arrays():
    rgb = np.stack([synthetic_array(3)] * 3, axis=-1)
    assert _image.from_array(rgb).width == 320
    original = synthetic_array(3)
    floats = original.astype(np.float32) / 255.0  # [0, 1] floats are scaled back to 0-255
    restored = np.frombuffer(_image.from_array(floats).pixels, dtype=np.uint8).reshape(original.shape)
    assert np.abs(restored.astype(int) - original.astype(int)).max() <= 1


def test_bad_array_shape():
    with pytest.raises(ImageError, match="2-D"):
        _image.from_array(np.zeros((4, 4, 4, 4), dtype=np.uint8))


@pytest.mark.parametrize(
    "data,match",
    [
        (b"", "empty"),
        (b"not an image" * 20, "Unrecognised"),
    ],
)
def test_garbage(data, match):
    with pytest.raises(ImageError, match=match):
        _image.from_bytes(data)


def test_truncated():
    data = synthetic_image(3)
    with pytest.raises(ImageError, match="corrupt"):
        _image.from_bytes(data[: len(data) // 2])


def test_too_small():
    with pytest.raises(ImageError, match="at least"):
        _image.from_bytes(encode(Image.new("L", (20, 20)), "PNG"))


def chunk(kind: bytes, payload: bytes) -> bytes:
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload))


def test_decompression_bomb_rejected_before_decoding():
    ihdr = struct.pack(">IIBBBBB", 60000, 60000, 8, 0, 0, 0, 0)
    data = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(b"\0" * 64)) + chunk(b"IEND", b"")
    with pytest.raises(ImageError, match="pixel limit"):
        _image.from_bytes(data)


def test_missing_file():
    with pytest.raises(ImageError, match="Cannot read"):
        _image.from_path("definitely-missing.png")


def test_unsupported_type():
    with pytest.raises(ImageError, match="Unsupported image input"):
        _image.load(12345)
