# User guide

## Creating fingerprints

Feature extraction (finding the ridge endings and bifurcations, called
*minutiae*) runs when you create a `Fingerprint`. Do it once per image and
keep the result.

```python
from pysourceafis import Fingerprint

fp = Fingerprint.from_file("finger.png")  # PNG, JPEG, BMP, TIFF, GIF, WebP...
fp = Fingerprint.from_bytes(uploaded_bytes)  # e.g. a web upload
fp = Fingerprint.from_image(pil_image_or_array)  # Pillow image or numpy array
fp = Fingerprint.from_pixels(w, h, raw_bytes)  # 8-bit grayscale, 0 = black

fp.minutiae_count  # very low values (< 10-15) usually mean a poor image
```

**Resolution matters.** SourceAFIS expects 500 dpi images, which is what most
optical scanners produce. If your images are different, pass `dpi=`:
`Fingerprint.from_file("scan.png", dpi=1000)`. pysourceafis does not trust dpi
metadata in files, because image editors often write wrong values.

Images are validated before decoding (size limits, decompression-bomb
protection, corrupt files) and raise `ImageError` with an explanation.

## Comparing two fingerprints (1:1, verification)

```python
from pysourceafis import RECOMMENDED_THRESHOLD

score = probe.match(candidate)
same_finger = score >= RECOMMENDED_THRESHOLD  # 40.0
```

The score is a **similarity**, unbounded and not a probability: identical
templates score in the hundreds, unrelated fingers usually below 20.
SourceAFIS documents that threshold 40 corresponds to roughly a 0.01% false
match rate in 1:1 comparison; it is a starting point, not a guarantee for
your sensor and population.

To compare one probe against many candidates yourself, reuse a `Matcher`
(it prepares the probe once):

```python
from pysourceafis import Matcher

matcher = Matcher(probe)
scores = [matcher.match(c) for c in candidates]  # thread-safe
```

## Searching a gallery (1:N, identification)

```python
from pysourceafis import Gallery

gallery = Gallery()  # uses all CPU cores
gallery.add(("alice", "right-index"), fp_alice)  # any hashable key
gallery.add_many(items)  # faster for many

gallery.search(probe, top_k=5)  # best 5, any score
gallery.search(probe, top_k=5, min_score=60)  # only strong candidates
gallery.identify(probe, threshold=60)  # best match or None
gallery.last_search  # SearchStats(comparisons, milliseconds)
gallery.remove(key)
len(gallery)
key in gallery
```

`search` compares the probe with **every** fingerprint (exact search). Cost
grows linearly: as a reference, a 2-core 2015 laptop compares about 19,000
fingerprints per second, so 10,000 fingerprints take about 0.5 s; a modern
16-core server is roughly ten times faster.

**Thresholds for 1:N.** Every extra fingerprint in the gallery is another
chance of a false match. With a per-comparison false match rate *f* and *N*
fingerprints, the chance that an unknown person matches someone is about
`1 - (1 - f) ** N`. With f = 0.01% (threshold 40) and N = 10,000 that is
already 63%. Use a clearly higher threshold for identification and calibrate
it on representative data: collect genuine pairs (two captures of the same
finger) and impostor pairs, compute their scores, and pick the threshold that
gives an acceptable false match rate *at your gallery size*.

**Memory.** Each fingerprint in a gallery uses about 12 KB of Java memory
(SourceAFIS keeps search structures); 100,000 fingerprints need about 1.2 GB.
Raise the Java memory limit with `PYSOURCEAFIS_JVM_OPTIONS=-Xmx4g` if needed.

## Storing templates

Templates are small (about 0.5 KB) and are what you should store - extracting
from images again is much slower.

```python
data = fp.to_bytes()  # bytes for your database
fp = Fingerprint.from_template(data)  # restore

# Rebuild a gallery at start-up from stored templates (deserialized in parallel)
failed_keys = gallery.add_templates(rows)  # rows = [(key, template_bytes), ...]
```

* Encrypt stored templates (for example AES-GCM with the record id as
  associated data) and restrict access: they are biometric data.
* Templates record the SourceAFIS version. `from_template` raises
  `TemplateError` for templates from another version, because SourceAFIS
  templates are not compatible across versions. Keep the original images
  (encrypted) if you need to re-extract after upgrading pysourceafis.

See [examples/03_store_templates.py](../examples/03_store_templates.py).

## Using it in web applications

* Create the `Gallery` once at start-up and share it; it is thread-safe.
* Extraction and matching run in Java without holding the GIL; in async
  frameworks call them through `run_in_executor` / `asyncio.to_thread` so the
  event loop stays responsive.
* See [examples/04_fastapi_service.py](../examples/04_fastapi_service.py).

## Errors

All exceptions inherit from `pysourceafis.SourceAfisError`:

| Exception | Meaning |
|---|---|
| `ImageError` | the input is not a usable image (also a `ValueError`) |
| `TemplateError` | invalid template bytes or another SourceAFIS version |
| `JavaNotFoundError` | no Java 11+ found (see installation) |
| `EngineError` | the engine could not start or failed |
| `readers.ReaderError` and subclasses | USB reader problems |

## Testing without real fingerprints

`pysourceafis.testing` (needs numpy) generates synthetic fingerprint-like
images: `synthetic_image(finger=7, impression=0)`. The same `finger` with a
different `impression` behaves like two captures of one finger. Use them in
tests and bug reports - never share real fingerprints - but do not use them to
claim accuracy on real data.
