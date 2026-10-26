"""
USB fingerprint readers (Windows, through the Windows Biometric Framework).

    >>> from pysourceafis.readers import list_readers, Reader
    >>> list_readers()                                   # doctest: +SKIP
    [ReaderInfo(unit_id=37, name='SecuGen fingerprint device', manufacturer='SecuGen Corporation', ...)]
    >>> with Reader() as reader:                         # doctest: +SKIP
    ...     capture = reader.capture(timeout=20)         # place a finger on the reader
    ...     fp = capture.fingerprint()                   # a pysourceafis.Fingerprint

Requirements and limitations (Microsoft's WBF rules, not pysourceafis choices):

* **Windows only.** macOS and Linux are not supported yet.
* Windows releases raw fingerprint images only to processes running as
  **Administrator** (or Local System). Run your script from an elevated
  terminal, otherwise :class:`ReaderPermissionError` is raised.
* A capture completes only for the program that has *biometric focus*. Console
  programs get it by bringing their console window to the front (done
  automatically); Windows services running as Local System use
  ``focus="service"``.
* The reader's WBF driver must return 8-bit uncompressed raw images. Tested
  with the SecuGen Hamster Pro 20 (USB VID 1162 / PID 2200, also sold by M2SYS
  as model HU20): 300 x 400 pixels at 500 dpi.
* A raw image does not prove that a live finger was present.
"""

from __future__ import annotations

import sys
import threading
import time
from dataclasses import dataclass

from ..errors import SourceAfisError


class ReaderError(SourceAfisError):
    """Base class for fingerprint reader problems."""


class ReaderUnavailableError(ReaderError):
    """No usable reader (unsupported OS, no device, or biometrics disabled)."""


class ReaderPermissionError(ReaderError):
    """The process may not read raw fingerprint images (needs Administrator)."""


class CaptureTimeout(ReaderError):
    """No finger was detected before the timeout."""


@dataclass(frozen=True)
class ReaderInfo:
    unit_id: int
    name: str
    manufacturer: str
    model: str
    device_id: str

    @property
    def usb_id(self) -> str:
        """e.g. ``VID_1162&PID_2200``."""
        parts = self.device_id.split("\\")
        return parts[1] if len(parts) > 1 else self.device_id


@dataclass(frozen=True)
class Capture:
    """One raw image from a reader. It is biometric data: do not log or keep it longer than needed."""

    width: int
    height: int
    pixels: bytes  # 8-bit grayscale, row-major, 0 = black
    dpi: int
    reader: ReaderInfo

    def fingerprint(self):
        """Extract a :class:`pysourceafis.Fingerprint` from this capture."""
        from ..fingerprint import Fingerprint

        return Fingerprint.from_pixels(self.width, self.height, self.pixels, dpi=self.dpi)

    def to_image(self):
        """The capture as a Pillow image (mode ``L``)."""
        from PIL import Image

        return Image.frombytes("L", (self.width, self.height), self.pixels)

    def save(self, path) -> None:
        """Save as PNG (or any format Pillow infers from the file name), keeping the dpi."""
        self.to_image().save(path, dpi=(self.dpi, self.dpi))


def _backend():
    if sys.platform != "win32":
        raise ReaderUnavailableError(
            f"Fingerprint readers are only supported on Windows for now (this is {sys.platform}). "
            "You can still capture images with your reader's own software and use Fingerprint.from_file()."
        )
    from . import _winbio

    return _winbio


def _info(unit) -> ReaderInfo:
    return ReaderInfo(unit.unit_id, unit.description, unit.manufacturer, unit.model, unit.device_instance_id)


def list_readers() -> list[ReaderInfo]:
    """Fingerprint readers registered with Windows (including built-in laptop sensors)."""
    wb = _backend()
    try:
        return [_info(u) for u in wb.enumerate_units()]
    except wb.WinBioError as exc:
        raise ReaderUnavailableError(str(exc)) from None


def is_elevated() -> bool:
    """True when this process can capture raw images (Administrator)."""
    return sys.platform == "win32" and _backend().is_admin()


class Reader:
    """
    One USB fingerprint reader.

    ``unit_id`` selects a reader from :func:`list_readers`; by default the first
    external USB reader is used (SecuGen readers are preferred, built-in laptop
    sensors are only used when they are the only device). Captures from other
    sensors are ignored, so touching a laptop's own sensor does not count.
    """

    def __init__(self, unit_id: int | None = None, focus: str = "console"):
        if focus not in ("console", "service", "none"):
            raise ValueError("focus must be 'console', 'service' or 'none'.")
        self._wb = _backend()
        readers = list_readers()
        if not readers:
            raise ReaderUnavailableError("No fingerprint reader is connected.")
        if unit_id is None:
            units = self._wb.enumerate_units()
            preferred = [u for u in units if u.is_secugen] or [u for u in units if "USB" in u.device_instance_id]
            chosen = (preferred or units)[0]
            self.info = _info(chosen)
        else:
            match = [r for r in readers if r.unit_id == unit_id]
            if not match:
                raise ReaderUnavailableError(
                    f"No reader with unit id {unit_id}; available: {[r.unit_id for r in readers]}."
                )
            self.info = match[0]
        self.focus = focus
        self._lock = threading.Lock()

    def capture(self, timeout: float = 20.0) -> Capture:
        """Wait for a finger on this reader and return the raw image."""
        wb = self._wb
        if not self._lock.acquire(blocking=False):
            raise ReaderError("Another capture is already running on this reader.")
        try:
            deadline = time.monotonic() + timeout
            try:
                session = wb.Session()
            except wb.WinBioError as exc:
                if exc.hr == wb.E_ACCESSDENIED:
                    raise ReaderPermissionError(
                        "Windows only gives raw fingerprint images to programs running as Administrator. "
                        "Run your script from an elevated terminal (Run as administrator)."
                    ) from None
                raise ReaderUnavailableError(str(exc)) from None
            with session, _Focus(wb, self.focus):
                timer = threading.Timer(timeout, session.cancel)
                timer.start()
                try:
                    while True:
                        try:
                            raw = session.capture()
                        except wb.WinBioError as exc:
                            if exc.hr == wb.WINBIO_E_CANCELED:
                                raise CaptureTimeout(f"No finger detected within {timeout:.0f} s.") from None
                            if exc.hr == wb.WINBIO_E_BAD_CAPTURE and time.monotonic() < deadline:
                                continue  # poor placement: keep waiting until the timeout
                            raise ReaderError(str(exc)) from None
                        except ValueError as exc:  # unsupported raw format
                            raise ReaderUnavailableError(f"{self.info.name}: {exc}") from None
                        if raw.unit_id != self.info.unit_id:
                            continue  # finger on another sensor in the pool
                        return Capture(raw.width, raw.height, raw.pixels, raw.dpi_x or 500, self.info)
                finally:
                    timer.cancel()
        finally:
            self._lock.release()

    def close(self) -> None:
        """Readers hold no open resources between captures; provided for symmetry."""

    def __enter__(self) -> Reader:
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def __repr__(self) -> str:
        return f"<Reader {self.info.manufacturer} {self.info.model} unit={self.info.unit_id}>"


class _Focus:
    """Biometric focus: WBF delivers system-pool captures only to the focused program."""

    def __init__(self, wb, mode: str):
        self.wb, self.mode = wb, mode

    def __enter__(self):
        if self.mode == "service":
            self.wb.acquire_focus()
        elif self.mode == "console":
            self.wb.focus_console_window()
        return self

    def __exit__(self, *exc):
        if self.mode == "service":
            self.wb.release_focus()


__all__ = [
    "Capture",
    "CaptureTimeout",
    "Reader",
    "ReaderError",
    "ReaderInfo",
    "ReaderPermissionError",
    "ReaderUnavailableError",
    "is_elevated",
    "list_readers",
]
