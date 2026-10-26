"""
Finding Java and starting the JVM - automatically, once per process.

Lookup order for the Java runtime (first match with Java >= 11 wins):

1. ``PYSOURCEAFIS_JAVA_HOME`` environment variable
2. ``JAVA_HOME`` environment variable
3. the ``jdk4py`` package (installed automatically by pip on Windows x64,
   macOS and Linux x64/arm64)
4. ``java`` on ``PATH``
5. common installation directories

The JVM starts lazily on first use. It cannot survive ``fork()``: a process
that forked after the JVM started must not use pysourceafis (use
``multiprocessing`` with the "spawn" start method, or start the JVM in each
worker, e.g. gunicorn without ``--preload``).

Environment variables:

* ``PYSOURCEAFIS_JAVA_HOME`` - Java installation to use
* ``PYSOURCEAFIS_JVM_OPTIONS`` - extra JVM options, e.g. ``-Xmx4g``
"""
from __future__ import annotations

import glob
import os
import platform
import re
import shlex
import shutil
import subprocess
import sys
import threading
from dataclasses import dataclass
from pathlib import Path

from .errors import EngineError, JavaNotFoundError

MIN_JAVA = 11
JARS_DIR = Path(__file__).resolve().parent / "_jars"
BRIDGE_JAR = "pysourceafis-bridge.jar"

_lock = threading.Lock()
_started_pid: int | None = None
_java: JavaRuntime | None = None


@dataclass(frozen=True)
class JavaRuntime:
    home: Path
    jvm_library: Path
    version: int
    source: str


def _jvm_library(home: Path) -> Path | None:
    if sys.platform == "win32":
        names = ["bin/server/jvm.dll", "bin/client/jvm.dll", "jre/bin/server/jvm.dll"]
    elif sys.platform == "darwin":
        names = ["lib/server/libjvm.dylib", "lib/libjli.dylib", "jre/lib/server/libjvm.dylib"]
    else:
        names = ["lib/server/libjvm.so", "jre/lib/server/libjvm.so",
                 f"lib/{platform.machine()}/server/libjvm.so"]
    for name in names:
        candidate = home / name
        if candidate.exists():
            return candidate
    return None


def _java_version(home: Path) -> int | None:
    """Major version from the 'release' file, or from `java -version`."""
    release = home / "release"
    if release.exists():
        m = re.search(r'JAVA_VERSION="(\d+)(?:\.(\d+))?', release.read_text(errors="replace"))
        if m:
            major = int(m.group(1))
            return int(m.group(2)) if major == 1 and m.group(2) else major
    exe = home / "bin" / ("java.exe" if sys.platform == "win32" else "java")
    if exe.exists():
        try:
            out = subprocess.run([str(exe), "-version"], capture_output=True, text=True, timeout=20).stderr
        except (OSError, subprocess.SubprocessError):
            return None
        m = re.search(r'version "(\d+)(?:\.(\d+))?', out)
        if m:
            major = int(m.group(1))
            return int(m.group(2)) if major == 1 and m.group(2) else major
    return None


def _candidates() -> list[tuple[str, Path]]:
    found: list[tuple[str, Path]] = []
    for var in ("PYSOURCEAFIS_JAVA_HOME", "JAVA_HOME"):
        value = os.environ.get(var)
        if value:
            found.append((var, Path(value)))
    try:
        import jdk4py  # type: ignore[import-not-found]

        found.append(("jdk4py", Path(jdk4py.JAVA_HOME)))
    except Exception:
        pass
    on_path = shutil.which("java")
    if on_path:
        # .../bin/java -> installation directory (resolving symlinks such as /usr/bin/java)
        found.append(("PATH", Path(os.path.realpath(on_path)).parent.parent))
    patterns = {
        "win32": [r"C:\Program Files\Eclipse Adoptium\*", r"C:\Program Files\Java\*",
                  r"C:\Program Files\Microsoft\jdk-*", r"C:\Program Files\Zulu\*"],
        "darwin": ["/Library/Java/JavaVirtualMachines/*/Contents/Home",
                   "/opt/homebrew/opt/openjdk*/libexec/openjdk.jdk/Contents/Home"],
    }.get(sys.platform, ["/usr/lib/jvm/*", "/usr/java/*", "/opt/java/*"])
    for pattern in patterns:
        for p in sorted(glob.glob(pattern), reverse=True):
            found.append(("system", Path(p)))
    return found


def find_java() -> JavaRuntime:
    """Locate a usable Java runtime without starting it."""
    tried = []
    for source, home in _candidates():
        lib = _jvm_library(home)
        version = _java_version(home) if lib else None
        tried.append(f"{source}: {home} -> " + ("no JVM library" if not lib else f"Java {version}"))
        if lib and version and version >= MIN_JAVA:
            return JavaRuntime(home=home, jvm_library=lib, version=version, source=source)
    raise JavaNotFoundError(
        f"No Java {MIN_JAVA}+ runtime found. Fix it with one of:\n"
        "  * pip install jdk4py            (Java packaged for Python)\n"
        "  * install Java from https://adoptium.net and set JAVA_HOME\n"
        "  * set PYSOURCEAFIS_JAVA_HOME to an existing Java installation\n"
        "Checked:\n  " + ("\n  ".join(tried) if tried else "(no candidates)")
    )


def jar_files() -> list[Path]:
    jars = sorted(JARS_DIR.glob("*.jar"))
    names = {j.name for j in jars}
    if BRIDGE_JAR not in names or not any(n.startswith("sourceafis-") for n in names):
        raise EngineError(
            f"The SourceAFIS jars are missing from {JARS_DIR}. If you installed from a source checkout, "
            "run `python tools/build_jars.py` first."
        )
    return jars


def ensure_started():
    """Start the JVM if needed and return the jpype module."""
    global _started_pid, _java
    import jpype

    if jpype.isJVMStarted():
        if _started_pid is not None and _started_pid != os.getpid():
            raise EngineError(
                "pysourceafis was started before this process was forked; the JVM does not survive fork(). "
                "Use multiprocessing with the 'spawn' start method, or import/use pysourceafis only inside "
                "each worker process (e.g. gunicorn without --preload)."
            )
        return jpype
    with _lock:
        if jpype.isJVMStarted():
            return jpype
        java = find_java()
        jars = jar_files()
        import jpype.config

        # Python threads attached to the JVM would otherwise block interpreter exit.
        jpype.config.destroy_jvm = False
        options = ["-Djava.awt.headless=true"]
        options += shlex.split(os.environ.get("PYSOURCEAFIS_JVM_OPTIONS", ""))
        try:
            jpype.startJVM(str(java.jvm_library), *options, classpath=[str(j) for j in jars],
                           convertStrings=True)
        except Exception as exc:
            raise EngineError(f"Could not start Java {java.version} from {java.home}: {exc}") from exc
        _silence_slf4j(jpype)
        _started_pid = os.getpid()
        _java = java
        return jpype


def _silence_slf4j(jpype) -> None:
    """
    SourceAFIS depends on the SLF4J API without a logging backend, so SLF4J prints a
    3-line "No SLF4J providers were found" notice on first use. Initialise it once
    with System.err muted; real errors later on are unaffected.
    """
    system = jpype.JClass("java.lang.System")
    original = system.err
    try:
        null_stream = jpype.JClass("java.io.PrintStream")(jpype.JClass("java.io.OutputStream").nullOutputStream())
        system.setErr(null_stream)
        jpype.JClass("org.slf4j.LoggerFactory").getILoggerFactory()
    except Exception:
        pass
    finally:
        system.setErr(original)


def runtime_info() -> JavaRuntime | None:
    """The Java runtime in use, if the JVM has been started by pysourceafis."""
    return _java
