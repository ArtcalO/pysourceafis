# pysourceafis documentation

pysourceafis is a Python wrapper around **SourceAFIS for Java**, an open-source
fingerprint recognition engine by Robert Važan. It compares fingerprint
images and returns a similarity score; on top of that it offers fast
in-memory 1:N search and USB reader capture on Windows.

| Page | Read it when you want to... |
|---|---|
| [Installation](installation.md) | install it, understand how Java is found, fix setup problems |
| [User guide](guide.md) | compare and search fingerprints, store templates, choose a threshold |
| [Fingerprint readers](readers.md) | capture from a USB scanner (Windows) |
| [Command line](cli.md) | use `pysourceafis` from a terminal or scripts |
| [Examples](../examples/README.md) | copy working code |

## Thirty-second tour

```python
from pysourceafis import Fingerprint, Gallery

a = Fingerprint.from_file("a.png")  # extract features once
b = Fingerprint.from_file("b.png")
a.match(b)  # -> 183.2  (similarity, not a probability)

gallery = Gallery()  # 1:N search
gallery.add("alice", a)
gallery.search(b, top_k=5)  # -> [Match(key='alice', score=183.2)]

data = a.to_bytes()  # store the template (~0.5 KB)...
a2 = Fingerprint.from_template(data)  # ...and load it later without the image
```

## Important to know

* **Scores are similarity scores, not probabilities.** A threshold of 40 is
  the SourceAFIS starting point for 1:1 comparison; calibrate on your own data,
  and use a *higher* threshold for 1:N search (see the guide).
* **Templates are biometric data.** They are not anonymous and cannot be
  "changed" like a password. Encrypt them at rest and never log them.
* **No liveness detection.** An image does not prove a live finger was present.
* **Templates are tied to the SourceAFIS version.** Keep the original images
  if you may need to re-extract after an upgrade.
