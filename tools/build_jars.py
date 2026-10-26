#!/usr/bin/env python3
"""
Build the Java side of pysourceafis into src/pysourceafis/_jars/.

    python tools/build_jars.py            # fetch jars + compile the bridge
    python tools/build_jars.py --check    # only verify what is already there

1. Fetches SourceAFIS for Java and its runtime dependencies (pinned versions)
   from the local Maven cache (~/.m2) when present, otherwise from Maven
   Central, and verifies every file against a pinned SHA-256 checksum.
2. Compiles java/src into pysourceafis-bridge.jar with `javac --release 11`
   (SourceAFIS 3.18.1 itself targets Java 11).

Requires a JDK 11+ (javac + jar) on PATH or in JAVA_HOME. Only the standard
library is used, so it runs before any dependency is installed.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "src" / "pysourceafis" / "_jars"
JAVA_SRC = ROOT / "java" / "src"
CACHE = ROOT / ".jar-cache"
MAVEN_CENTRAL = "https://repo1.maven.org/maven2"
BRIDGE_JAR = "pysourceafis-bridge.jar"

SOURCEAFIS_VERSION = "3.18.1"

# (group, artifact, version, sha256) - runtime dependency closure of
# com.machinezoo.sourceafis:sourceafis:3.18.1 (from its POM). Checksums were
# computed from Maven Central artifacts whose SHA-1 matched Central's .sha1 files.
ARTIFACTS = [
    ("com.machinezoo.sourceafis", "sourceafis", SOURCEAFIS_VERSION,
     "850582c842a7c7bf4ab87d8e8785674d9e092eb379a021d46bc053d2fc6028c0"),
    ("com.machinezoo.fingerprintio", "fingerprintio", "1.3.1",
     "2c2b1e3a35eb12317a75966e2b33e27d68d6b79e21120de8220f9fb20b20429c"),
    ("com.machinezoo.noexception", "noexception", "1.9.1",
     "29b002c8ccb17e73f06e2a237b083a38ca8e83cf833e0483c2366ff492965a8d"),
    ("com.machinezoo.closeablescope", "closeablescope", "1.0.1",
     "3e3554e56a831a68e168ee0e267b7e5ede9a9623c5814065888de49de0debfc8"),
    ("com.machinezoo.stagean", "stagean", "1.3.0",
     "19a77e39c6db01950c6caedc72323995f4be38368a16f72ffce5ea49ef3c7650"),
    ("it.unimi.dsi", "fastutil", "8.5.12",
     "b5543ee08d062d551cf0a5c9bc0fb70588b0382079029ba48941fa9c9be8a5d4"),
    ("commons-io", "commons-io", "2.15.0",
     "a328dad730921d197b6a9b195dffa00e41c974c2dac8fe37e84d31706bca7792"),
    ("com.google.code.gson", "gson", "2.10.1",
     "4241c14a7727c34feea6507ec801318a3d4a90f070e4525681079fb94ee4c593"),
    ("com.fasterxml.jackson.core", "jackson-databind", "2.15.3",
     "c3c53333a2172a80678bda1803e39cff45bec6ae3e9c7d4f44a81ec4e2ab18dc"),
    ("com.fasterxml.jackson.core", "jackson-core", "2.15.3",
     "51fab7aad51ed588482edc507fd542747936c5094d1ab76ed21ddb63b96b610d"),
    ("com.fasterxml.jackson.core", "jackson-annotations", "2.15.3",
     "aae865c3d88256d61b11523cb1e88bd48d5b9ad5855fa1fc859504fd2204708a"),
    ("com.fasterxml.jackson.dataformat", "jackson-dataformat-cbor", "2.15.3",
     "b8c7ae4a9d82e3fd0aecfd4599f42eaf503d0faf99e2f97abfb8b2c33bc09da7"),
    ("com.github.mhshams", "jnbis", "2.1.2",
     "275046559dbfcf11adf0811fcc71646627f00964b8421029b2d1e8340b292fe5"),
    ("org.slf4j", "slf4j-api", "2.0.9",
     "0818930dc8d7debb403204611691da58e49d42c50b6ffcfdce02dadb7c3c2b6c"),
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def jar_name(artifact: str, version: str) -> str:
    return f"{artifact}-{version}.jar"


def maven_path(group: str, artifact: str, version: str) -> str:
    return f"{group.replace('.', '/')}/{artifact}/{version}/{jar_name(artifact, version)}"


def fetch(group: str, artifact: str, version: str, expected: str) -> Path:
    target = OUT / jar_name(artifact, version)
    if target.exists() and sha256(target) == expected:
        return target
    rel = maven_path(group, artifact, version)
    candidates = [Path.home() / ".m2" / "repository" / rel, CACHE / jar_name(artifact, version)]
    for local in candidates:
        if local.exists() and sha256(local) == expected:
            shutil.copyfile(local, target)
            print(f"  {target.name:42s} (local cache)")
            return target
    url = f"{MAVEN_CENTRAL}/{rel}"
    CACHE.mkdir(exist_ok=True)
    tmp = CACHE / (jar_name(artifact, version) + ".part")
    print(f"  {target.name:42s} downloading {url}")
    with urllib.request.urlopen(url, timeout=120) as r, open(tmp, "wb") as f:
        shutil.copyfileobj(r, f)
    actual = sha256(tmp)
    if actual != expected:
        tmp.unlink(missing_ok=True)
        raise SystemExit(f"Checksum mismatch for {url}\n  expected {expected}\n  got      {actual}")
    tmp.replace(CACHE / jar_name(artifact, version))
    shutil.copyfile(CACHE / jar_name(artifact, version), target)
    return target


def find_tool(name: str) -> str:
    exe = name + (".exe" if os.name == "nt" else "")
    java_home = os.environ.get("JAVA_HOME")
    if java_home and (Path(java_home) / "bin" / exe).exists():
        return str(Path(java_home) / "bin" / exe)
    found = shutil.which(name)
    if found:
        return found
    raise SystemExit(f"'{name}' not found. Install a JDK 11+ (e.g. https://adoptium.net) and put it on PATH "
                     "or set JAVA_HOME.")


def build_bridge(classpath: list[Path]) -> Path:
    javac, jar = find_tool("javac"), find_tool("jar")
    sources = sorted(str(p) for p in JAVA_SRC.rglob("*.java"))
    with tempfile.TemporaryDirectory() as tmp:
        classes = Path(tmp) / "classes"
        classes.mkdir()
        cp = os.pathsep.join(str(p) for p in classpath)
        subprocess.run([javac, "--release", "11", "-Xlint:all", "-Werror", "-encoding", "UTF-8",
                        "-cp", cp, "-d", str(classes), *sources], check=True)
        target = OUT / BRIDGE_JAR
        target.unlink(missing_ok=True)
        subprocess.run([jar, "--create", "--file", str(target), "-C", str(classes), "."], check=True)
    print(f"  {BRIDGE_JAR:42s} compiled from {len(sources)} source files")
    return target


SHRINK = {"fastutil"}  # libraries trimmed to the classes reachable from SourceAFIS and the bridge


def shrunk_name(artifact: str, version: str) -> str:
    return f"{artifact}-{version}-min.jar"


def shrink(full_jar: Path, other_jars: list[Path]) -> Path:
    """
    Keep only the classes of ``full_jar`` that are transitively reachable from
    ``other_jars`` (class-level dependency analysis with the JDK's jdeps tool).
    fastutil is ~23 MB but SourceAFIS uses a small part of it; the test suite
    exercises extraction, serialization and matching on the trimmed jar.
    """
    import re
    import zipfile

    jdeps = find_tool("jdeps")
    edge = re.compile(r"^\s+(\S+)\s+->\s+(\S+)\s")
    artifact, version = full_jar.stem.rsplit("-", 1)
    target = OUT / shrunk_name(artifact, version)
    target.unlink(missing_ok=True)  # an old trimmed copy would be a duplicate module for jdeps

    def edges(targets: list[Path]) -> list[tuple[str, str]]:
        # SourceAFIS is a named module, so jdeps must resolve modules: give it the jar folder.
        result = subprocess.run([jdeps, "-verbose:class", "-filter:none", "--multi-release", "11", "--ignore-missing-deps",
                                 "--module-path", str(full_jar.parent), *[str(t) for t in targets]],
                                capture_output=True, text=True)
        if result.returncode != 0:
            raise SystemExit(f"jdeps failed:\n{result.stdout}\n{result.stderr}")
        return [(m.group(1), m.group(2)) for m in map(edge.match, result.stdout.splitlines()) if m]

    prefix = "it.unimi.dsi.fastutil."
    roots = {dst for _, dst in edges(other_jars) if dst.startswith(prefix)}
    graph: dict[str, set[str]] = {}
    for src, dst in edges([full_jar]):
        if dst.startswith(prefix):
            graph.setdefault(src, set()).add(dst)
    keep, stack = set(), list(roots)
    while stack:
        cls = stack.pop()
        if cls in keep:
            continue
        keep.add(cls)
        stack.extend(graph.get(cls, ()))
    outers = {c.split("$")[0] for c in keep}

    with zipfile.ZipFile(full_jar) as src, zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            name = info.filename
            if name.endswith(".class"):
                cls = name[:-6].replace("/", ".")
                if cls.split("$")[0] not in outers:  # keep nested classes of kept classes
                    continue
            elif not (name.startswith("META-INF/") and not name.endswith((".SF", ".RSA", ".DSA"))):
                continue
            dst.writestr(info, src.read(name))
    print(f"  {target.name:42s} {len(outers)} of the library's classes kept "
          f"({target.stat().st_size / 1e6:.1f} MB instead of {full_jar.stat().st_size / 1e6:.1f} MB)")
    return target


def check() -> int:
    missing = []
    for group, artifact, version, expected in ARTIFACTS:
        if artifact in SHRINK:
            p = OUT / shrunk_name(artifact, version)
            if not p.exists():
                missing.append(p.name)
            continue
        p = OUT / jar_name(artifact, version)
        if not p.exists() or sha256(p) != expected:
            missing.append(p.name)
    if not (OUT / BRIDGE_JAR).exists():
        missing.append(BRIDGE_JAR)
    if missing:
        print("Missing or invalid: " + ", ".join(missing))
        return 1
    print(f"All {len(ARTIFACTS) + 1} jars present and verified in {OUT}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="Verify existing jars without building.")
    args = ap.parse_args()
    if args.check:
        return check()
    OUT.mkdir(parents=True, exist_ok=True)
    print(f"SourceAFIS {SOURCEAFIS_VERSION} and dependencies -> {OUT}")
    jars = [fetch(*a) for a in ARTIFACTS]
    bridge = build_bridge(jars)
    final = set()
    for (group, artifact, version, _), jar in zip(ARTIFACTS, jars):
        if artifact in SHRINK:
            others = [j for j in jars if j != jar] + [bridge]
            final.add(shrink(jar, others).name)
            jar.unlink()  # the verified full jar is kept in .jar-cache / ~/.m2, not shipped
        else:
            final.add(jar.name)
    final.add(BRIDGE_JAR)
    for stale in OUT.glob("*.jar"):
        if stale.name not in final:
            stale.unlink()
    return check()


if __name__ == "__main__":
    sys.exit(main())
