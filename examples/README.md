# Examples

All examples except 04 and 05 run without real fingerprints: they use the
synthetic generator (`pip install "pysourceafis[testing]"`).

| File | Shows |
|---|---|
| [01_compare.py](01_compare.py) | 1:1 comparison and the threshold decision; pass two image paths to use your own |
| [02_gallery_search.py](02_gallery_search.py) | 1:N search, `identify()`, search statistics, an unknown person |
| [03_store_templates.py](03_store_templates.py) | storing templates in SQLite with the engine version, rebuilding a gallery at start-up |
| [04_fastapi_service.py](04_fastapi_service.py) | a small web service (needs `fastapi uvicorn python-multipart`) |
| [05_capture_from_reader.py](05_capture_from_reader.py) | USB reader capture, enrollment and identification (Windows, Administrator) |

Run them from the repository root, e.g. `python examples/02_gallery_search.py`.
Examples 01-03 are executed by the test suite, so they stay correct.
