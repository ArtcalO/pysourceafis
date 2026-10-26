# Changelog

All notable changes to pysourceafis are documented in this file. These entries
are the project's **release notes**.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
the project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
While the version is 0.x, minor releases may contain breaking changes; they are
always listed under **Changed** or **Removed**.

How to add an entry: see "Release notes" in [CONTRIBUTING.md](CONTRIBUTING.md).

## [Unreleased]

### Added

- `Fingerprint`: extract a template from a file, encoded bytes, file object,
  Pillow image, numpy array or raw pixels; `match()` returns the SourceAFIS
  similarity score; `to_bytes()` / `from_template()` store and restore templates
  (version-checked); pickling support for multiprocessing.
- `Matcher` for fast repeated 1:1 comparisons against one probe (thread-safe).
- `Gallery`: thread-safe in-memory 1:N search on all CPU cores with any hashable
  keys, `top_k`, `min_score`, `identify()`, bulk loading of stored templates.
- Automatic Java handling: uses `PYSOURCEAFIS_JAVA_HOME`, `JAVA_HOME`, the
  `jdk4py` package (installed automatically on Windows x64, macOS and Linux
  x64/arm64), `java` on PATH or common install locations; clear error when a
  process uses pysourceafis after `fork()`.
- Bundled SourceAFIS for Java 3.18.1 and its dependencies (no Maven needed).
- `pysourceafis.testing`: synthetic fingerprint generator for tests and examples.
- Project structure, license, contribution guide and release notes.
