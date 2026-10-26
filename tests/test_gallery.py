from concurrent.futures import ThreadPoolExecutor

import pytest

from pysourceafis import RECOMMENDED_THRESHOLD, Gallery, Match


@pytest.fixture
def gallery(make_fp):
    g = Gallery(threads=2)
    g.add_many([(f"person-{i}", make_fp(i, 0)) for i in range(1, 11)])
    yield g
    g.close()


def test_search_ranks_mate_first(gallery, make_fp):
    hits = gallery.search(make_fp(4, 1), top_k=3)
    assert len(hits) == 3 and isinstance(hits[0], Match)
    assert hits[0].key == "person-4"
    assert [h.score for h in hits] == sorted((h.score for h in hits), reverse=True)
    assert gallery.last_search.comparisons == 10


def test_min_score_and_identify(gallery, make_fp):
    assert gallery.search(make_fp(99, 0), min_score=RECOMMENDED_THRESHOLD) == []
    assert gallery.identify(make_fp(4, 1), RECOMMENDED_THRESHOLD).key == "person-4"
    assert gallery.identify(make_fp(99, 0), RECOMMENDED_THRESHOLD) is None


def test_scores_equal_one_to_one(gallery, make_fp):
    probe = make_fp(4, 1)
    assert gallery.search(probe, top_k=1)[0].score == pytest.approx(probe.match(make_fp(4, 0)))


def test_keys_any_hashable(make_fp):
    with Gallery() as g:
        g.add(("alice", "right-index"), make_fp(1, 0))
        g.add(42, make_fp(2, 0))
        assert g.search(make_fp(1, 1), top_k=1)[0].key == ("alice", "right-index")
        assert set(g.keys()) == {("alice", "right-index"), 42}
        with pytest.raises(TypeError):
            g.add(["unhashable"], make_fp(3, 0))


def test_replace_remove_clear(gallery, make_fp):
    gallery.add("person-4", make_fp(7, 0))  # replace
    assert len(gallery) == 10
    assert gallery.search(make_fp(7, 1), top_k=2)[0].key in {"person-4", "person-7"}
    assert gallery.remove("person-4") and not gallery.remove("person-4")
    assert "person-4" not in gallery and len(gallery) == 9
    gallery.clear()
    assert len(gallery) == 0 and gallery.search(make_fp(1, 0)) == []


def test_empty_gallery(make_fp):
    with Gallery() as g:
        assert g.search(make_fp(1, 0)) == [] and g.last_search.comparisons == 0


def test_items_and_template_bulk_load(gallery, make_fp):
    stored = [(k, fp.to_bytes()) for k, fp in gallery.items()]
    with Gallery() as g:
        failed = g.add_templates(stored + [("broken", b"junk")])
        assert failed == ["broken"] and len(g) == 10 and "broken" not in g
        assert g.search(make_fp(4, 1), top_k=1)[0].key == "person-4"


def test_validation(gallery, make_fp):
    with pytest.raises(TypeError):
        gallery.search("probe")
    with pytest.raises(ValueError):
        gallery.search(make_fp(1, 0), top_k=0)
    with pytest.raises(TypeError):
        gallery.add("x", "not a fingerprint")


def test_concurrent_search_and_mutation(gallery, make_fp):
    probe = make_fp(4, 1)

    def mutate(i):
        gallery.add(f"tmp-{i}", make_fp(20 + i % 5, 0))
        gallery.remove(f"tmp-{i}")

    with ThreadPoolExecutor(6) as pool:
        futures = [pool.submit(mutate, i) for i in range(20)]
        searches = [pool.submit(lambda: gallery.search(probe, top_k=1)[0].key) for _ in range(20)]
        [f.result() for f in futures]
        assert {f.result() for f in searches} == {"person-4"}
    assert len(gallery) == 10


def test_memory_estimate(gallery):
    assert gallery.memory_bytes > 10 * 5_000
