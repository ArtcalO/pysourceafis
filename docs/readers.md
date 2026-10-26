# Fingerprint readers

`pysourceafis.readers` captures images from USB fingerprint readers on
**Windows**, through the Windows Biometric Framework (WBF) that Windows uses
for Windows Hello. No vendor SDK is needed.

```python
from pysourceafis.readers import Reader, list_readers

print(list_readers())

with Reader() as reader:  # first USB reader
    capture = reader.capture(timeout=20)  # waits for a finger
    fp = capture.fingerprint()  # pysourceafis.Fingerprint
    capture.save("finger.png")  # optional; it is biometric data
```

From a terminal:

```bash
pysourceafis readers
pysourceafis capture -o finger.png -t finger.template
```

## Requirements

| Requirement | Why |
|---|---|
| Windows 10/11 | WBF is a Windows API; macOS and Linux are not supported yet |
| Reader with a WBF driver that returns raw 8-bit images | standard for Windows Hello compatible USB readers |
| **Run as Administrator** | Windows only releases *raw* fingerprint images to Administrator / Local System processes |
| Program has biometric focus | handled automatically for console programs (the console window is brought to the front) |

Without Administrator rights you get `ReaderPermissionError` with this
explanation. For a background service, run your program as Local System and
use `Reader(focus="service")`.

## Tested hardware

| Reader | USB id | Result |
|---|---|---|
| SecuGen Hamster Pro 20 (also sold by M2SYS as model HU20) | VID_1162 & PID_2200 | 300 x 400 px at 500 dpi; 36-40 minutiae from live captures |

Reports for other readers are very welcome (open an issue with the output of
`pysourceafis readers` - never attach a fingerprint image).

## Behaviour

* `Reader()` picks the first SecuGen reader, else the first USB reader, else
  the only sensor. Use `Reader(unit_id=...)` with an id from `list_readers()`.
* A finger placed on another sensor (for example the laptop's own reader) is
  ignored; the capture keeps waiting for the selected reader.
* Poorly placed fingers are retried automatically until the timeout, which
  raises `CaptureTimeout`.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `ReaderPermissionError` | start the terminal or IDE with "Run as administrator" |
| capture never completes | another app (Windows Security, Settings > Sign-in options) holds biometric focus: close it |
| `ReaderUnavailableError: ... encoding` / `E_NOTIMPL` | the reader's driver does not provide raw images through WBF; use the vendor SDK to save images and `Fingerprint.from_file()` |
| `WINBIO_E_INVALID_OPERATION` | a "secure" sensor (Enhanced Sign-in Security) blocks raw capture on this PC |
