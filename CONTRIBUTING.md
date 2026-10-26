# Contributing to pysourceafis

Thank you for considering a contribution! Bug reports, documentation fixes,
tests, new examples and features are all welcome. You do not need to ask for
permission before opening an issue or a pull request.

## Ground rules

- Be kind and constructive - see the [Code of Conduct](CODE_OF_CONDUCT.md).
- **Never commit real fingerprint images or templates**, not even your own.
  Fingerprints are personal biometric data. Use the synthetic generator in
  `pysourceafis.testing` for tests, examples and bug reports.
- Report security problems privately - see [SECURITY.md](SECURITY.md).
- By contributing you agree that your contribution is licensed under the
  [Apache License 2.0](LICENSE), like the rest of the project.

## Development setup

You need **Python 3.10+**, **git** and a **JDK 11 or newer** (for example
[Eclipse Temurin](https://adoptium.net)) on `PATH` or in `JAVA_HOME`.

The JDK is a contributor-only requirement: `tools/build_jars.py` uses `javac`
to compile the Java bridge and `jdeps` to trim the bundled fastutil jar, and
neither tool is part of the Java runtime that `jdk4py` installs for users.
People who `pip install pysourceafis` do not need a JDK.

```bash
git clone https://github.com/<your-fork>/pysourceafis.git
cd pysourceafis
python -m venv .venv
# Windows:  .venv\Scripts\activate      Linux/macOS:  source .venv/bin/activate
python tools/build_jars.py        # fetches + verifies SourceAFIS jars, compiles the bridge
pip install -e ".[dev]"           # (also runs build_jars.py automatically if jars are missing)
pytest
```

Check your JDK with `javac -version` (must print 11 or higher). The first
`build_jars.py` run downloads about 30 MB from Maven Central into `.jar-cache/`
(or reuses `~/.m2` if you use Maven); later runs work offline.

`python -m pysourceafis doctor` prints what pysourceafis detects on your machine
(Python, Java, jars, engine version) and how to fix problems.

## Project layout

| Path | What it contains |
|---|---|
| `src/pysourceafis/` | the Python package (public API in `__init__.py`) |
| `src/pysourceafis/_jars/` | generated: SourceAFIS + dependencies + bridge jar (not in git) |
| `java/` | the small Java bridge (parallel 1:N search) compiled into `pysourceafis-bridge.jar` |
| `tools/build_jars.py` | downloads pinned, checksum-verified jars from Maven Central and builds the bridge |
| `tests/` | pytest suite (uses the real engine with synthetic fingerprints) |
| `docs/`, `examples/` | user documentation and runnable examples |

## Making a change

1. Open or pick an issue, or describe the change in your pull request.
2. Create a branch: `git checkout -b fix/short-description`.
3. Write the code **and a test** that fails without your change.
4. Run the checks locally:

   ```bash
   ruff check . && ruff format --check .
   pytest
   ```

5. Add a line to `CHANGELOG.md` under **[Unreleased]** (see below).
6. Commit with a clear message (imperative mood: "Add Gallery.remove", not
   "added..."). Small, focused commits are easier to review.
7. Push and open a pull request. Fill in the template; CI runs the tests on
   Windows, macOS and Linux.

## Coding guidelines

- Public API lives in `pysourceafis/__init__.py`; everything starting with `_`
  is internal and may change without notice.
- Type hints on all public functions; keep `py.typed` accurate.
- Errors raised to users must be subclasses of `pysourceafis.SourceAfisError`
  with a message that says what to do next.
- Do not leak Java/JPype types through the public API.
- Similarity scores are **not probabilities** - keep that wording in docs.

## Release notes

Every user-visible change needs a `CHANGELOG.md` entry under `## [Unreleased]`,
in one of these sections: **Added**, **Changed**, **Deprecated**, **Removed**,
**Fixed**, **Security**. Write it for users ("`Gallery.search` accepts
`threshold`"), not for developers ("refactor search loop"). Internal changes
(CI, tests) usually need no entry.

## Releasing (maintainers)

1. Move the **[Unreleased]** entries to a new section `## [X.Y.Z] - YYYY-MM-DD`
   and update the comparison links at the bottom of `CHANGELOG.md`.
2. Bump `version` in `src/pysourceafis/_version.py`.
3. Commit (`Release X.Y.Z`), tag (`git tag vX.Y.Z`) and push the tag. The
   release workflow builds the wheel and source distribution, runs the tests
   and publishes to PyPI through trusted publishing; the GitHub release text
   is taken from the changelog section.

## Updating SourceAFIS

Bump `SOURCEAFIS_VERSION` and the pinned dependency list (with SHA-256
checksums) in `tools/build_jars.py`, run the tests, and note the change under
**Changed** - templates from different SourceAFIS versions are not compatible,
so users must re-extract stored templates.
