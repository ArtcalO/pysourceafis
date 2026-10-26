import json

import pytest

from pysourceafis.cli import main


@pytest.fixture
def files(tmp_path, make_png):
    gallery = tmp_path / "gallery"
    gallery.mkdir()
    for i in range(1, 6):
        (gallery / f"finger{i}.png").write_bytes(make_png(i, 0))
    (tmp_path / "probe.png").write_bytes(make_png(3, 1))
    (tmp_path / "bad.png").write_bytes(b"nope")
    return tmp_path


def test_doctor(capsys):
    assert main(["doctor"]) == 0
    out = capsys.readouterr().out
    assert "SourceAFIS: 3.18.1" in out and "Everything looks good." in out


def test_compare_json(files, capsys):
    assert main(["compare", str(files / "probe.png"), str(files / "gallery/finger3.png"), "--json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["match"] is True and result["score"] > 40


def test_extract_then_identify_with_templates(files, capsys):
    assert main(["extract", str(files / "gallery/finger3.png"), "-o", str(files / "gallery/t3.template")]) == 0
    capsys.readouterr()
    assert main(["identify", str(files / "probe.png"), str(files / "gallery"), "--top-k", "2", "--json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert {c["key"] for c in result["candidates"]} == {"finger3.png", "t3.template"}


def test_errors_exit_nonzero(files, capsys):
    assert main(["compare", str(files / "bad.png"), str(files / "probe.png")]) == 1
    assert "Unrecognised image format" in capsys.readouterr().err
