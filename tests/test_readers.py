"""Reader tests. No hardware needed: the WBF layer is replaced by a fake; the parser gets synthetic buffers."""

import ctypes
import sys

import pytest

from pysourceafis import readers
from pysourceafis.readers import _winbio
from pysourceafis.testing import synthetic_array

SECUGEN = _winbio.Unit(37, 1, 0, 1, r"USB\VID_1162&PID_2200\5&BD", "SecuGen fingerprint device",
                       "SecuGen Corporation", "SDU05", "", "1.0")  # fmt: skip
LAPTOP = _winbio.Unit(38, 1, 0, 0x41, r"USB\VID_138A&PID_0017\4D", "Synaptics FP Sensors",
                      "Validity Sensors, Inc.", "x", "", "1.0")  # fmt: skip


def make_bir(width=4, height=3, pixels=None, depth=8, compression=0, scale_units=1, res=500, fmt=0x46495200):
    pixels = pixels if pixels is not None else bytes(range(width * height))
    hdr = _winbio.WINBIO_BDB_ANSI_381_HEADER()
    hdr.FormatIdentifier, hdr.VersionNumber = fmt, 0x30313000
    hdr.HorizontalImageResolution = hdr.VerticalImageResolution = res
    hdr.ElementCount, hdr.ScaleUnits, hdr.PixelDepth, hdr.ImageCompressionAlg = 1, scale_units, depth, compression
    rec = _winbio.WINBIO_BDB_ANSI_381_RECORD()
    rec.HorizontalLineLength, rec.VerticalLineLength = width, height
    block = bytes(hdr) + bytes(rec) + pixels
    bir = _winbio.WINBIO_BIR()
    bir.StandardDataBlock.Offset, bir.StandardDataBlock.Size = ctypes.sizeof(bir), len(block)
    return bytes(bir) + block


def test_parse_raw_bir():
    img = _winbio.parse_raw_bir(make_bir(), unit_id=37)
    assert (img.width, img.height, img.dpi_x, img.unit_id, img.pixels) == (4, 3, 500, 37, bytes(range(12)))
    assert _winbio.parse_raw_bir(make_bir(scale_units=2, res=197), 1).dpi_x == 500


@pytest.mark.parametrize(
    "kwargs,match",
    [({"fmt": 1}, "format identifier"), ({"depth": 16}, "encoding"), ({"compression": 1}, "encoding"),
     ({"pixels": b"\0" * 5}, "Truncated")],
)  # fmt: skip
def test_parse_raw_bir_rejects(kwargs, match):
    with pytest.raises(ValueError, match=match):
        _winbio.parse_raw_bir(make_bir(**kwargs), 1)


def test_struct_sizes_match_windows_layout():
    assert ctypes.sizeof(_winbio.WINBIO_BIR) == 32
    assert ctypes.sizeof(_winbio.WINBIO_BDB_ANSI_381_HEADER) == 40
    assert ctypes.sizeof(_winbio.WINBIO_BDB_ANSI_381_RECORD) == 16


class FakeSession:
    def __init__(self, results):
        self.results = list(results)

    def capture(self):
        r = self.results.pop(0)
        if isinstance(r, Exception):
            raise r
        return r

    def cancel(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        pass


@pytest.fixture
def fake_wbf(monkeypatch):
    """Pretend to be Windows with a SecuGen reader and a laptop sensor."""
    state = {"results": [], "admin": True}

    def session():
        if not state["admin"]:
            raise _winbio.WinBioError("WinBioOpenSession", _winbio.E_ACCESSDENIED)
        return FakeSession(state["results"])

    monkeypatch.setattr(readers, "sys", type("S", (), {"platform": "win32"}))
    monkeypatch.setattr(_winbio, "enumerate_units", lambda: [LAPTOP, SECUGEN])
    monkeypatch.setattr(_winbio, "Session", session)
    monkeypatch.setattr(_winbio, "is_admin", lambda: state["admin"])
    monkeypatch.setattr(_winbio, "focus_console_window", lambda: None)
    return state


def raw(unit_id, finger=3):
    arr = synthetic_array(finger)
    return _winbio.RawImage(arr.shape[1], arr.shape[0], arr.tobytes(), 500, 500, unit_id)


def test_list_and_default_reader_prefers_usb_reader(fake_wbf):
    assert [r.unit_id for r in readers.list_readers()] == [38, 37]
    reader = readers.Reader()
    assert reader.info.unit_id == 37 and reader.info.usb_id == "VID_1162&PID_2200"


def test_capture_ignores_other_sensor_and_bad_placement(fake_wbf):
    fake_wbf["results"] = [raw(38), _winbio.WinBioError("cap", _winbio.WINBIO_E_BAD_CAPTURE, 7), raw(37)]
    capture = readers.Reader().capture(timeout=5)
    assert (capture.width, capture.height, capture.dpi) == (320, 400, 500)
    assert capture.reader.unit_id == 37
    assert capture.fingerprint().minutiae_count > 10


def test_capture_timeout(fake_wbf):
    fake_wbf["results"] = [_winbio.WinBioError("cap", _winbio.WINBIO_E_CANCELED)]
    with pytest.raises(readers.CaptureTimeout):
        readers.Reader().capture(timeout=1)


def test_permission_error_explains_administrator(fake_wbf):
    fake_wbf["admin"] = False
    with pytest.raises(readers.ReaderPermissionError, match="Administrator"):
        readers.Reader().capture()


def test_unknown_unit(fake_wbf):
    with pytest.raises(readers.ReaderUnavailableError, match="unit id 99"):
        readers.Reader(unit_id=99)


def test_capture_save(fake_wbf, tmp_path):
    fake_wbf["results"] = [raw(37)]
    path = tmp_path / "capture.png"
    readers.Reader().capture().save(path)
    from PIL import Image

    with Image.open(path) as img:
        assert img.size == (320, 400) and round(img.info["dpi"][0]) == 500


def test_non_windows_is_explained(monkeypatch):
    monkeypatch.setattr(readers, "sys", type("S", (), {"platform": "linux"}))
    with pytest.raises(readers.ReaderUnavailableError, match="only supported on Windows"):
        readers.list_readers()


@pytest.mark.skipif(sys.platform != "win32", reason="real WBF enumeration needs Windows")
def test_real_enumeration_does_not_crash():
    try:
        result = readers.list_readers()
    except readers.ReaderUnavailableError:
        pytest.skip("Windows Biometric Framework not available")
    assert all(isinstance(r, readers.ReaderInfo) for r in result)
