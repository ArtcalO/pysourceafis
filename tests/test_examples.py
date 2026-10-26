"""The examples are part of the documentation: make sure they keep working."""

import runpy
import sys
from pathlib import Path

import pytest

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


@pytest.mark.parametrize("name", ["01_compare.py", "02_gallery_search.py", "03_store_templates.py"])
def test_example_runs(name, monkeypatch, tmp_path, capsys):
    args = [str(tmp_path / "demo.sqlite")] if name.startswith("03") else []
    monkeypatch.setattr(sys, "argv", [name, *args])
    runpy.run_path(str(EXAMPLES / name), run_name="__main__")
    out = capsys.readouterr().out
    expected = {"01": "same finger", "02": "identified: person-017", "03": "best match: Match(key=('person-4'"}
    assert expected[name[:2]] in out, out


def test_fastapi_example_imports_when_available():
    pytest.importorskip("fastapi")
    pytest.importorskip("multipart")
    runpy.run_path(str(EXAMPLES / "04_fastapi_service.py"))


def test_reader_example_is_valid_python():
    compile((EXAMPLES / "05_capture_from_reader.py").read_text(encoding="utf-8"), "05", "exec")
