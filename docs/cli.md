# Command line

Installed as `pysourceafis`; also available as `python -m pysourceafis`.

| Command | What it does |
|---|---|
| `pysourceafis doctor` | checks JPype, Java, jars, engine; runs a synthetic self-test |
| `pysourceafis version` | pysourceafis and SourceAFIS versions |
| `pysourceafis compare A B` | similarity score of two images or templates |
| `pysourceafis extract IMAGE [-o OUT]` | save the template of an image (default `IMAGE.template`) |
| `pysourceafis identify PROBE FOLDER [--top-k 5]` | search a probe in a folder of images and templates (recursive) |
| `pysourceafis readers` | list fingerprint readers (Windows) |
| `pysourceafis capture [-o IMG] [-t TEMPLATE] [--unit N] [--timeout S]` | capture from a USB reader (Windows, Administrator) |

Common options:

* `--dpi 500` - image resolution (images only)
* `--threshold 40` - decision threshold for `compare` / `identify`
* `--json` - machine-readable output for `compare` / `identify`

Files ending in `.template`, `.bin` or `.cbor` are treated as templates, all
others as images. Exit code is 0 on success and 1 on errors (the message is
printed to stderr).

```bash
$ pysourceafis compare probe.png alice.png
144.23  (MATCH at threshold 40.0)

$ pysourceafis identify probe.png people/ --top-k 3
Searched 1200 fingerprints in 95 ms
  1.   144.23  alice/right-index.png  MATCH
  2.    11.02  bob/left-thumb.png
  3.     9.87  carol/right-index.template
```
