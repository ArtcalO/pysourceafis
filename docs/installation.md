# Installation

```bash
pip install pysourceafis
python -m pysourceafis doctor
```

`doctor` checks every piece (JPype, Java, the bundled jars, the engine) and
runs a self-test with synthetic fingerprints. If something is missing it says
how to fix it. Install `pysourceafis[testing]` (adds numpy) to enable the
self-test.

## Requirements

* Python 3.10 or newer
* A Java runtime 11 or newer - **installed automatically** on most platforms (below)

Nothing else: the SourceAFIS engine and its dependencies are bundled in the
package (about 5 MB), so no Maven and no internet access at run time.

## How Java is found

pysourceafis starts the Java engine inside your Python process (through
[JPype](https://jpype.readthedocs.io/)) the first time you use it. It looks for
a Java runtime in this order and uses the first one that is version 11+:

1. `PYSOURCEAFIS_JAVA_HOME` - set this to force a specific Java
2. `JAVA_HOME`
3. the [`jdk4py`](https://pypi.org/project/jdk4py/) package - a Java runtime
   shipped as a Python wheel, installed automatically with pysourceafis on
   **Windows x64, macOS (Intel and Apple Silicon) and Linux x64/arm64 (glibc)**
4. `java` on `PATH`
5. common install folders (`C:\Program Files\Eclipse Adoptium\...`,
   `/usr/lib/jvm/...`, `/Library/Java/JavaVirtualMachines/...`)

On other platforms (Windows on ARM, Alpine/musl Linux, ...) install Java 11+
yourself, for example from [adoptium.net](https://adoptium.net), and set
`JAVA_HOME`.

## Environment variables

| Variable | Effect |
|---|---|
| `PYSOURCEAFIS_JAVA_HOME` | Java installation to use (highest priority) |
| `PYSOURCEAFIS_JVM_OPTIONS` | extra JVM options, e.g. `-Xmx8g` for large galleries |

## Processes, threads and servers

* **Threads:** everything is thread-safe. Matching runs in Java threads that do
  not hold the Python GIL, so a threaded web server scales well.
* **fork():** the Java engine cannot survive `fork()`. If a process uses
  pysourceafis and then forks, the child gets a clear `EngineError`. Use
  `multiprocessing` with the `"spawn"` start method (the default on Windows and
  macOS), or load pysourceafis only inside each worker.
* **gunicorn:** do not use `--preload`; prefer `--workers 1 --threads N` (one
  gallery in memory) or one gallery per worker if memory allows.
* `Fingerprint` objects can be pickled (the template is sent), so they can be
  passed between processes.

## Troubleshooting

| Problem | Fix |
|---|---|
| `JavaNotFoundError` | `pip install jdk4py`, or install Java 11+ and set `JAVA_HOME` |
| `EngineError: ... jars are missing` | you installed from a source checkout: run `python tools/build_jars.py` |
| `EngineError: ... forked` | see "Processes" above |
| `OutOfMemoryError` with a big gallery | `PYSOURCEAFIS_JVM_OPTIONS=-Xmx8g` (about 12 KB per fingerprint) |
| First call takes 1-4 s | that is the Java start-up, once per process |
