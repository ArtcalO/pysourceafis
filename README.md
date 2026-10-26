# pysourceafis

**Fingerprint matching for Python, powered by [SourceAFIS](https://sourceafis.machinezoo.com/).**

`pysourceafis` brings the SourceAFIS fingerprint recognition engine to Python
with a small, Pythonic API. It runs the official SourceAFIS for Java engine
in-process and takes care of the plumbing (Java runtime, jars, JVM lifecycle,
image decoding) so you can compare and search fingerprints in a few lines.

> **Unofficial project.** pysourceafis is a community wrapper. It is not made
> or endorsed by the SourceAFIS author. All credit for the algorithm goes to
> Robert Važan and the SourceAFIS project.

> **Status: alpha (0.x).** The API may still change before 1.0.

## Installation

```bash
pip install pysourceafis
```

## Quick start

```python
from pysourceafis import Fingerprint, Gallery

probe = Fingerprint.from_file("probe.png")
candidate = Fingerprint.from_file("candidate.png")
print(probe.match(candidate))            # similarity score (not a probability)

gallery = Gallery()
gallery.add("alice", Fingerprint.from_file("alice.png"))
gallery.add("bob", Fingerprint.from_file("bob.png"))
for hit in gallery.search(probe, top_k=3):
    print(hit.key, hit.score)
```

## Contributing

Contributions are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md) to set up a
development environment, run the tests and send a pull request. Release
notes are kept in [CHANGELOG.md](CHANGELOG.md).

## License

Apache License 2.0 - see [LICENSE](LICENSE) and [NOTICE](NOTICE).
SourceAFIS is also distributed under the Apache License 2.0.
