"""In-memory 1:N fingerprint search."""
from __future__ import annotations

import itertools
import threading
from collections.abc import Hashable, Iterable, Iterator
from typing import NamedTuple

from . import _java
from .fingerprint import Fingerprint


class Match(NamedTuple):
    """One search result: the key you used in :meth:`Gallery.add` and the similarity score."""

    key: Hashable
    score: float


class SearchStats(NamedTuple):
    comparisons: int
    milliseconds: float


class Gallery:
    """
    A collection of fingerprints that can be searched with a probe (1:N identification).

    Keys can be any hashable value (a user id, a ``(person, finger)`` tuple, ...).
    Search compares the probe with **every** fingerprint, in parallel on all
    CPU cores, so its cost grows linearly with the gallery size. Memory use is
    about 12 KB per fingerprint (SourceAFIS keeps search structures in memory).

    The gallery is thread-safe: you can add or remove fingerprints while
    other threads search.

    >>> gallery = Gallery()
    >>> gallery.add("alice", Fingerprint.from_file("alice.png"))      # doctest: +SKIP
    >>> gallery.search(Fingerprint.from_file("probe.png"), top_k=3)   # doctest: +SKIP
    [Match(key='alice', score=183.2)]
    """

    def __init__(self, threads: int | None = None):
        """``threads``: matching threads per search (default: all CPU cores)."""
        self._j = _java.ensure_started().JClass("io.github.pysourceafis.Gallery")(int(threads or 0))
        self._lock = threading.RLock()
        self._ids = itertools.count(1)
        self._key_to_id: dict[Hashable, int] = {}
        self._id_to_key: dict[int, Hashable] = {}
        self.last_search: SearchStats | None = None

    # ------------------------------------------------------------- mutation
    def add(self, key: Hashable, fingerprint: Fingerprint) -> None:
        """Add a fingerprint, replacing any fingerprint stored under the same key."""
        self.add_many([(key, fingerprint)])

    def add_many(self, items: Iterable[tuple[Hashable, Fingerprint]]) -> None:
        """Add many ``(key, fingerprint)`` pairs at once (faster than repeated :meth:`add`)."""
        jpype = _java.ensure_started()
        pairs = list(items)
        for key, fp in pairs:
            if not isinstance(fp, Fingerprint):
                raise TypeError(f"Expected a Fingerprint for key {key!r}, got {type(fp).__name__}.")
            hash(key)
        with self._lock:
            ids = [self._id_for(key) for key, _ in pairs]
            templates = jpype.JArray(jpype.JClass("com.machinezoo.sourceafis.FingerprintTemplate"))(
                [fp._jt for _, fp in pairs])
            self._j.putAll(jpype.JArray(jpype.JLong)(ids), templates)

    def add_templates(self, items: Iterable[tuple[Hashable, bytes]]) -> list[Hashable]:
        """
        Bulk-load serialized templates (from :meth:`Fingerprint.to_bytes`), deserializing
        them in parallel. Returns the keys whose templates were invalid (they are skipped).
        """
        jpype = _java.ensure_started()
        pairs = [(k, bytes(d)) for k, d in items]
        with self._lock:
            ids = [self._id_for(k) for k, _ in pairs]
            blobs = jpype.JArray(jpype.JArray(jpype.JByte))(len(pairs))
            for i, (_, d) in enumerate(pairs):
                blobs[i] = jpype.JArray(jpype.JByte)(d)
            failed = [pairs[int(i)][0] for i in self._j.putAllSerialized(jpype.JArray(jpype.JLong)(ids), blobs)]
            for key in failed:
                self._forget(key)
        return failed

    def remove(self, key: Hashable) -> bool:
        """Remove a fingerprint. Returns False if the key was not present."""
        with self._lock:
            jid = self._key_to_id.get(key)
            if jid is None:
                return False
            self._j.remove(jid)
            self._forget(key)
            return True

    def clear(self) -> None:
        with self._lock:
            self._j.clear()
            self._key_to_id.clear()
            self._id_to_key.clear()

    # --------------------------------------------------------------- access
    def __len__(self) -> int:
        return int(self._j.size())

    def __contains__(self, key: Hashable) -> bool:
        return key in self._key_to_id

    def __iter__(self) -> Iterator[Hashable]:
        return iter(list(self._key_to_id))

    def keys(self) -> list[Hashable]:
        return list(self._key_to_id)

    def get(self, key: Hashable) -> Fingerprint | None:
        jid = self._key_to_id.get(key)
        jt = self._j.get(jid) if jid is not None else None
        return Fingerprint(jt) if jt is not None else None

    def items(self) -> Iterator[tuple[Hashable, Fingerprint]]:
        """Iterate over ``(key, fingerprint)`` pairs, e.g. to persist the gallery."""
        for key in self.keys():
            fp = self.get(key)
            if fp is not None:
                yield key, fp

    @property
    def memory_bytes(self) -> int:
        """Estimated memory used by the stored templates."""
        return int(self._j.memory())

    # --------------------------------------------------------------- search
    def search(self, probe: Fingerprint, top_k: int = 10, min_score: float = 0.0) -> list[Match]:
        """
        Compare ``probe`` with every fingerprint and return the best ``top_k``
        matches with a score of at least ``min_score``, best first.

        The best match is **not** automatically the same finger: decide with a
        calibrated threshold (``min_score``). False matches become more likely as
        the gallery grows, so 1:N search needs a higher threshold than 1:1.
        """
        if not isinstance(probe, Fingerprint):
            raise TypeError("search() expects a Fingerprint probe.")
        if top_k < 1:
            raise ValueError("top_k must be at least 1.")
        result = self._j.search(probe._jt, int(top_k), float(min_score))
        self.last_search = SearchStats(int(result.comparisons), result.nanos / 1e6)
        out = []
        for jid, score in zip(result.ids, result.scores):
            jid = int(jid)
            if jid in self._id_to_key:  # skip entries removed while the search was running
                out.append(Match(self._id_to_key[jid], float(score)))
        return out

    def identify(self, probe: Fingerprint, threshold: float) -> Match | None:
        """The best match if its score reaches ``threshold``, otherwise None."""
        hits = self.search(probe, top_k=1, min_score=threshold)
        return hits[0] if hits else None

    # ------------------------------------------------------------ lifecycle
    def close(self) -> None:
        """Stop the gallery's matching threads. The gallery cannot be used afterwards."""
        self._j.close()

    def __enter__(self) -> Gallery:
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def __repr__(self) -> str:
        return f"<Gallery size={len(self)}>"

    # ------------------------------------------------------------- internals
    def _id_for(self, key: Hashable) -> int:
        jid = self._key_to_id.get(key)
        if jid is None:
            jid = next(self._ids)
            self._key_to_id[key] = jid
            self._id_to_key[jid] = key
        return jid

    def _forget(self, key: Hashable) -> None:
        jid = self._key_to_id.pop(key, None)
        if jid is not None:
            self._id_to_key.pop(jid, None)


__all__ = ["Gallery", "Match", "SearchStats"]
