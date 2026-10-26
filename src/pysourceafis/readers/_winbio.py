"""
Minimal ctypes binding to the Windows Biometric Framework (winbio.dll) for
capturing RAW fingerprint images from a WBF sensor such as the SecuGen
Hamster Pro 20 (USB VID 1162 / PID 2200, sold by M2SYS as model HU20).

Documented constraints (Microsoft Learn, WinBioCaptureSample):
* raw capture requires a session opened with WINBIO_FLAG_RAW, and
  "only applications running under the Administrators and Local System
  accounts have the necessary privileges";
* in the system pool the call blocks until the calling application has
  window focus and a finger is presented;
* it fails with WINBIO_E_INVALID_OPERATION when a secure sensor is in the pool.

Struct layouts follow the documented Winbio_types.h definitions.
"""

from __future__ import annotations

import ctypes
import sys
from ctypes import POINTER, Structure, byref, c_size_t, c_ubyte, c_ulong, c_ulonglong, c_ushort, c_void_p, c_wchar
from dataclasses import dataclass

WINBIO_TYPE_FINGERPRINT = 0x00000008
WINBIO_POOL_SYSTEM = 1
WINBIO_POOL_PRIVATE = 2
WINBIO_FLAG_DEFAULT = 0x00000000
WINBIO_FLAG_RAW = 0x00000001
WINBIO_DATA_FLAG_RAW = 0x20
WINBIO_NO_PURPOSE_AVAILABLE = 0x00
WINBIO_DB_DEFAULT = c_void_p(1)

E_ACCESSDENIED = 0x80070005
E_NOTIMPL = 0x80004001
E_INVALIDARG = 0x80070057
WINBIO_E_BAD_CAPTURE = 0x80098008
WINBIO_E_CANCELED = 0x80098004
WINBIO_E_INVALID_OPERATION = 0x8009802C
WINBIO_E_NO_CAPTURE_DATA = 0x80098021
WINBIO_E_DISABLED = 0x80098024

HRESULT_NAMES = {
    E_ACCESSDENIED: "E_ACCESSDENIED (raw capture needs Administrator)",
    E_NOTIMPL: "E_NOTIMPL (sensor does not support raw capture)",
    E_INVALIDARG: "E_INVALIDARG",
    WINBIO_E_BAD_CAPTURE: "WINBIO_E_BAD_CAPTURE (place the finger again)",
    WINBIO_E_CANCELED: "WINBIO_E_CANCELED",
    WINBIO_E_INVALID_OPERATION: "WINBIO_E_INVALID_OPERATION (a secure sensor is in the system pool)",
    WINBIO_E_NO_CAPTURE_DATA: "WINBIO_E_NO_CAPTURE_DATA",
    WINBIO_E_DISABLED: "WINBIO_E_DISABLED (biometrics disabled by policy)",
}

REJECT_DETAIL = {
    1: "too high",
    2: "too low",
    3: "too left",
    4: "too right",
    5: "too fast",
    6: "too slow",
    7: "poor quality",
    8: "too skewed",
    9: "too short",
    10: "merge failure",
}


class WINBIO_VERSION(Structure):
    _fields_ = [("MajorVersion", c_ulong), ("MinorVersion", c_ulong)]


class WINBIO_UNIT_SCHEMA(Structure):
    _fields_ = [
        ("UnitId", c_ulong),
        ("PoolType", c_ulong),
        ("BiometricFactor", c_ulong),
        ("SensorSubType", c_ulong),
        ("Capabilities", c_ulong),
        ("DeviceInstanceId", c_wchar * 256),
        ("Description", c_wchar * 256),
        ("Manufacturer", c_wchar * 256),
        ("Model", c_wchar * 256),
        ("SerialNumber", c_wchar * 256),
        ("FirmwareVersion", WINBIO_VERSION),
    ]


class WINBIO_BIR_DATA(Structure):
    _fields_ = [("Size", c_ulong), ("Offset", c_ulong)]


class WINBIO_BIR(Structure):
    _fields_ = [
        ("HeaderBlock", WINBIO_BIR_DATA),
        ("StandardDataBlock", WINBIO_BIR_DATA),
        ("VendorDataBlock", WINBIO_BIR_DATA),
        ("SignatureBlock", WINBIO_BIR_DATA),
    ]


class WINBIO_REGISTERED_FORMAT(Structure):
    _fields_ = [("Owner", c_ushort), ("Type", c_ushort)]


class WINBIO_BDB_ANSI_381_HEADER(Structure):
    _fields_ = [
        ("RecordLength", c_ulonglong),
        ("FormatIdentifier", c_ulong),
        ("VersionNumber", c_ulong),
        ("ProductId", WINBIO_REGISTERED_FORMAT),
        ("CaptureDeviceId", c_ushort),
        ("ImageAcquisitionLevel", c_ushort),
        ("HorizontalScanResolution", c_ushort),
        ("VerticalScanResolution", c_ushort),
        ("HorizontalImageResolution", c_ushort),
        ("VerticalImageResolution", c_ushort),
        ("ElementCount", c_ubyte),
        ("ScaleUnits", c_ubyte),
        ("PixelDepth", c_ubyte),
        ("ImageCompressionAlg", c_ubyte),
        ("Reserved", c_ushort),
    ]


class WINBIO_BDB_ANSI_381_RECORD(Structure):
    _fields_ = [
        ("BlockLength", c_ulong),
        ("HorizontalLineLength", c_ushort),
        ("VerticalLineLength", c_ushort),
        ("Position", c_ubyte),
        ("CountOfViews", c_ubyte),
        ("ViewNumber", c_ubyte),
        ("ImageQuality", c_ubyte),
        ("ImpressionType", c_ubyte),
        ("Reserved", c_ubyte),
    ]


class WinBioError(RuntimeError):
    def __init__(self, where: str, hr: int, detail: int = 0):
        hr &= 0xFFFFFFFF
        self.hr = hr
        self.detail = detail
        name = HRESULT_NAMES.get(hr, "")
        extra = f"; reject detail: {REJECT_DETAIL.get(detail, detail)}" if detail else ""
        super().__init__(f"{where} failed: 0x{hr:08X} {name}{extra}")


@dataclass
class Unit:
    unit_id: int
    pool_type: int
    sensor_subtype: int
    capabilities: int
    device_instance_id: str
    description: str
    manufacturer: str
    model: str
    serial_number: str
    firmware: str

    @property
    def is_secugen(self) -> bool:
        return "VID_1162" in self.device_instance_id.upper() or "secugen" in self.manufacturer.lower()


@dataclass
class RawImage:
    width: int
    height: int
    pixels: bytes  # 8-bit grayscale, row-major
    dpi_x: int
    dpi_y: int
    unit_id: int


def _lib():
    if sys.platform != "win32":
        raise OSError("The Windows Biometric Framework is only available on Windows.")
    lib = ctypes.WinDLL("winbio.dll")
    lib.WinBioEnumBiometricUnits.argtypes = [c_ulong, POINTER(POINTER(WINBIO_UNIT_SCHEMA)), POINTER(c_size_t)]
    lib.WinBioOpenSession.argtypes = [c_ulong, c_ulong, c_ulong, POINTER(c_ulong), c_size_t, c_void_p, POINTER(c_ulong)]
    lib.WinBioCaptureSample.argtypes = [
        c_ulong,
        c_ubyte,
        c_ubyte,
        POINTER(c_ulong),
        POINTER(c_void_p),
        POINTER(c_size_t),
        POINTER(c_ulong),
    ]
    lib.WinBioCloseSession.argtypes = [c_ulong]
    lib.WinBioCancel.argtypes = [c_ulong]
    lib.WinBioFree.argtypes = [c_void_p]
    for name in (
        "WinBioEnumBiometricUnits",
        "WinBioOpenSession",
        "WinBioCaptureSample",
        "WinBioCloseSession",
        "WinBioCancel",
        "WinBioFree",
    ):
        getattr(lib, name).restype = ctypes.c_long
    return lib


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def enumerate_units() -> list[Unit]:
    lib = _lib()
    arr = POINTER(WINBIO_UNIT_SCHEMA)()
    count = c_size_t(0)
    hr = lib.WinBioEnumBiometricUnits(WINBIO_TYPE_FINGERPRINT, byref(arr), byref(count))
    if hr < 0:
        raise WinBioError("WinBioEnumBiometricUnits", hr)
    try:
        return [
            Unit(
                s.UnitId,
                s.PoolType,
                s.SensorSubType,
                s.Capabilities,
                s.DeviceInstanceId,
                s.Description,
                s.Manufacturer,
                s.Model,
                s.SerialNumber,
                f"{s.FirmwareVersion.MajorVersion}.{s.FirmwareVersion.MinorVersion}",
            )
            for s in (arr[i] for i in range(count.value))
        ]
    finally:
        lib.WinBioFree(arr)


def parse_raw_bir(buffer: bytes, unit_id: int) -> RawImage:
    """Extract the first 8-bit uncompressed image from an ANSI 381 standard data block."""
    bir = WINBIO_BIR.from_buffer_copy(buffer[: ctypes.sizeof(WINBIO_BIR)])
    off, size = bir.StandardDataBlock.Offset, bir.StandardDataBlock.Size
    if not size:
        raise ValueError("Sample has no standard (ANSI 381) data block; the driver may only return vendor data.")
    block = buffer[off : off + size]
    hdr = WINBIO_BDB_ANSI_381_HEADER.from_buffer_copy(block[: ctypes.sizeof(WINBIO_BDB_ANSI_381_HEADER)])
    if hdr.FormatIdentifier != 0x46495200:
        raise ValueError(f"Unexpected ANSI 381 format identifier 0x{hdr.FormatIdentifier:08X}.")
    if hdr.PixelDepth != 8 or hdr.ImageCompressionAlg != 0:
        raise ValueError(f"Unsupported image encoding (depth {hdr.PixelDepth}, compression {hdr.ImageCompressionAlg}).")
    rec_off = ctypes.sizeof(WINBIO_BDB_ANSI_381_HEADER)
    rec = WINBIO_BDB_ANSI_381_RECORD.from_buffer_copy(
        block[rec_off : rec_off + ctypes.sizeof(WINBIO_BDB_ANSI_381_RECORD)]
    )
    w, h = rec.HorizontalLineLength, rec.VerticalLineLength
    px_off = rec_off + ctypes.sizeof(WINBIO_BDB_ANSI_381_RECORD)
    pixels = bytes(block[px_off : px_off + w * h])
    if len(pixels) != w * h:
        raise ValueError(f"Truncated image: expected {w * h} bytes, got {len(pixels)}.")
    # ScaleUnits 1 = pixels per inch, 2 = pixels per centimetre.
    to_dpi = (lambda v: v) if hdr.ScaleUnits == 1 else (lambda v: round(v * 2.54))
    return RawImage(w, h, pixels, to_dpi(hdr.HorizontalImageResolution), to_dpi(hdr.VerticalImageResolution), unit_id)


class Session:
    """System-pool RAW session. Requires an elevated (Administrator) process."""

    def __init__(self):
        self._lib = _lib()
        self.handle = c_ulong(0)
        hr = self._lib.WinBioOpenSession(
            WINBIO_TYPE_FINGERPRINT, WINBIO_POOL_SYSTEM, WINBIO_FLAG_RAW, None, 0, WINBIO_DB_DEFAULT, byref(self.handle)
        )
        if hr < 0:
            raise WinBioError("WinBioOpenSession", hr)

    def capture(self) -> RawImage:
        """Blocks until a finger is placed on a sensor in the pool."""
        unit, sample, size, reject = c_ulong(0), c_void_p(), c_size_t(0), c_ulong(0)
        hr = self._lib.WinBioCaptureSample(
            self.handle,
            WINBIO_NO_PURPOSE_AVAILABLE,
            WINBIO_DATA_FLAG_RAW,
            byref(unit),
            byref(sample),
            byref(size),
            byref(reject),
        )
        try:
            if hr < 0:
                raise WinBioError("WinBioCaptureSample", hr, reject.value)
            data = ctypes.string_at(sample, size.value)
        finally:
            if sample:
                self._lib.WinBioFree(sample)
        return parse_raw_bir(data, unit.value)

    def cancel(self) -> None:
        self._lib.WinBioCancel(self.handle)

    def close(self) -> None:
        if self.handle.value:
            self._lib.WinBioCloseSession(self.handle)
            self.handle = c_ulong(0)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


# ------------------------------------------------------------------ focus


def focus_console_window() -> None:
    """Bring this console window to the foreground (WBF gives captures to the focused program)."""
    hwnd = ctypes.windll.kernel32.GetConsoleWindow()
    if hwnd:
        ctypes.windll.user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        ctypes.windll.user32.SetForegroundWindow(hwnd)


def acquire_focus() -> None:
    """WinBioAcquireFocus: for windowless processes running as Local System."""
    lib = _lib()
    lib.WinBioAcquireFocus.restype = ctypes.c_long
    hr = lib.WinBioAcquireFocus()
    if hr < 0:
        raise WinBioError("WinBioAcquireFocus (requires Local System)", hr)


def release_focus() -> None:
    lib = _lib()
    lib.WinBioReleaseFocus.restype = ctypes.c_long
    lib.WinBioReleaseFocus()
