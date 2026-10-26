import pickle
from concurrent.futures import ThreadPoolExecutor

import pytest

from pysourceafis import (
    RECOMMENDED_THRESHOLD,
    Fingerprint,
    ImageError,
    Matcher,
    TemplateError,
    engine_version,
)
from pysourceafis.testing import synthetic_array


def test_engine_version():
    assert engine_version() == "3.18.1"


def test_genuine_scores_higher_than_impostor(make_fp):
    a0, a1, b0 = make_fp(1, 0), make_fp(1, 1), make_fp(2, 0)
    assert a0.match(a1) > RECOMMENDED_THRESHOLD > a0.match(b0) >= 0
    assert a0.match(a0) > a0.match(a1)


def test_match_is_symmetric_enough(make_fp):
    a, b = make_fp(1, 0), make_fp(1, 1)
    assert a.match(b) == pytest.approx(b.match(a), rel=0.25)


def test_template_round_trip(make_fp):
    a = make_fp(1, 0)
    data = a.to_bytes()
    b = Fingerprint.from_template(data)
    assert b.to_bytes() == data
    assert b.match(a) == pytest.approx(a.match(a))
    assert a.minutiae_count > 10 and a.memory_bytes > len(data)


def test_pickle(make_fp):
    a = make_fp(1, 0)
    assert pickle.loads(pickle.dumps(a)).to_bytes() == a.to_bytes()


@pytest.mark.parametrize("data", [b"", b"junk", bytes(64)])
def test_invalid_templates(data):
    with pytest.raises(TemplateError):
        Fingerprint.from_template(data)


def test_template_from_other_engine_version_is_rejected(make_fp):
    cbor2 = pytest.importorskip("cbor2")
    obj = cbor2.loads(make_fp(1, 0).to_bytes())
    obj["version"] = "3.0.0-java"
    with pytest.raises(TemplateError, match="not compatible"):
        Fingerprint.from_template(cbor2.dumps(obj))


def test_from_pixels_and_dpi(make_png):
    arr = synthetic_array(5)
    fp = Fingerprint.from_pixels(arr.shape[1], arr.shape[0], arr.tobytes())
    assert fp.minutiae_count > 0
    with pytest.raises(ImageError):
        Fingerprint.from_pixels(10, 10, b"\0" * 5)
    with pytest.raises(ValueError, match="dpi"):
        Fingerprint.from_bytes(make_png(5), dpi=10)


def test_blank_image_has_no_minutiae():
    import numpy as np

    blank = Fingerprint.from_image(np.full((400, 320), 255, dtype=np.uint8))
    assert blank.minutiae_count == 0


def test_matcher_reuse_and_threads(make_fp):
    probe = make_fp(1, 1)
    candidates = [make_fp(i, 0) for i in range(1, 9)]
    matcher = Matcher(probe)
    expected = [matcher.match(c) for c in candidates]
    with ThreadPoolExecutor(8) as pool:
        assert list(pool.map(matcher.match, candidates * 3)) == expected * 3
    with pytest.raises(TypeError):
        matcher.match("not a fingerprint")
