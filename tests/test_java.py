import pytest

from pysourceafis import JavaNotFoundError, _java


def test_find_java_reports_source_and_version():
    java = _java.find_java()
    assert java.version >= 11 and java.jvm_library.exists()
    assert java.source in {"PYSOURCEAFIS_JAVA_HOME", "JAVA_HOME", "jdk4py", "PATH", "system"}


def test_explicit_java_home_wins(monkeypatch):
    real = _java.find_java()
    monkeypatch.setenv("PYSOURCEAFIS_JAVA_HOME", str(real.home))
    assert _java.find_java().source == "PYSOURCEAFIS_JAVA_HOME"


def test_helpful_error_when_no_java(monkeypatch, tmp_path):
    monkeypatch.setattr(_java, "_candidates", lambda: [("JAVA_HOME", tmp_path)])
    with pytest.raises(JavaNotFoundError, match="pip install jdk4py") as exc:
        _java.find_java()
    assert "no JVM library" in str(exc.value)


def test_old_java_rejected(monkeypatch, tmp_path):
    lib = tmp_path / (
        "bin/server/jvm.dll"
        if _java.sys.platform == "win32"
        else "lib/server/libjvm.dylib"
        if _java.sys.platform == "darwin"
        else "lib/server/libjvm.so"
    )
    lib.parent.mkdir(parents=True)
    lib.write_bytes(b"")
    (tmp_path / "release").write_text('JAVA_VERSION="1.8.0_392"')
    monkeypatch.setattr(_java, "_candidates", lambda: [("JAVA_HOME", tmp_path)])
    with pytest.raises(JavaNotFoundError, match="Java 8"):
        _java.find_java()


def test_jars_present():
    names = {p.name for p in _java.jar_files()}
    assert "pysourceafis-bridge.jar" in names and any(n.startswith("sourceafis-3.18.1") for n in names)


def test_fork_guard(monkeypatch):
    from pysourceafis import EngineError, engine_version

    engine_version()  # make sure the JVM runs
    monkeypatch.setattr(_java, "_started_pid", -1)
    with pytest.raises(EngineError, match="fork"):
        _java.ensure_started()


def test_public_api_is_pure_python():
    import pysourceafis

    for name in pysourceafis.__all__:
        module = getattr(getattr(pysourceafis, name), "__module__", "pysourceafis") or "pysourceafis"
        assert module.startswith("pysourceafis") or module == "builtins", (name, module)
