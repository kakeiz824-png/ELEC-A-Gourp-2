"""Shared TTL cache tests: expiry, bounding, and the cached-None distinction.

Time is driven through a fake clock rather than by sleeping, so the TTL is
tested exactly and the suite stays fast.
"""

import pytest

from app import cache as cache_module
from app.cache import MISS, TTLCache


@pytest.fixture()
def clock(monkeypatch):
    """A monotonic clock the test advances by hand."""
    now = {"t": 1000.0}
    monkeypatch.setattr(cache_module, "monotonic", lambda: now["t"])

    def advance(seconds: float) -> None:
        now["t"] += seconds

    return advance


def test_a_stored_value_is_returned_until_the_ttl_passes(clock) -> None:
    cache = TTLCache(ttl_seconds=100.0)
    cache.set(("k",), "value")

    clock(99.0)
    assert cache.get(("k",)) == "value"

    clock(1.0)  # exactly at the TTL: expired
    assert cache.get(("k",)) is MISS


def test_a_miss_is_distinguishable_from_a_cached_none(clock) -> None:
    """``None`` is a legitimate answer, so it must not read as "not cached"."""
    cache = TTLCache()
    cache.set(("stored",), None)

    assert cache.get(("stored",)) is None
    assert cache.get(("absent",)) is MISS


def test_compute_runs_only_on_a_miss(clock) -> None:
    cache = TTLCache(ttl_seconds=100.0)
    calls = {"count": 0}

    def compute():
        calls["count"] += 1
        return "value"

    assert cache.get_or_compute(("k",), compute) == "value"
    assert cache.get_or_compute(("k",), compute) == "value"
    assert calls["count"] == 1

    clock(100.0)
    assert cache.get_or_compute(("k",), compute) == "value"
    assert calls["count"] == 2


def test_a_raised_exception_is_not_cached() -> None:
    """A failure must be retried on the next call, not pinned for the TTL."""
    cache = TTLCache()
    calls = {"count": 0}

    def flaky():
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("boom")
        return "recovered"

    with pytest.raises(RuntimeError):
        cache.get_or_compute(("k",), flaky)

    assert cache.get_or_compute(("k",), flaky) == "recovered"
    assert calls["count"] == 2


def test_cache_none_false_recomputes_an_empty_answer() -> None:
    cache = TTLCache()
    calls = {"count": 0}

    def sometimes_empty():
        calls["count"] += 1
        return None if calls["count"] == 1 else "found"

    assert cache.get_or_compute(("k",), sometimes_empty, cache_none=False) is None
    assert cache.get_or_compute(("k",), sometimes_empty, cache_none=False) == "found"
    assert calls["count"] == 2


def test_the_cache_is_bounded() -> None:
    """At capacity the cache is dropped rather than growing without limit."""
    cache = TTLCache(max_entries=3)

    for index in range(3):
        cache.set((index,), index)
    assert len(cache) == 3

    cache.set(("overflow",), "value")

    assert len(cache) == 1
    assert cache.get(("overflow",)) == "value"
    assert cache.get((0,)) is MISS


def test_overwriting_an_existing_key_does_not_trigger_a_clear() -> None:
    """Refreshing a key already held is not growth, so the cache is kept."""
    cache = TTLCache(max_entries=2)
    cache.set(("a",), 1)
    cache.set(("b",), 2)

    cache.set(("a",), 99)

    assert len(cache) == 2
    assert cache.get(("a",)) == 99
    assert cache.get(("b",)) == 2


def test_clear_drops_everything() -> None:
    cache = TTLCache()
    cache.set(("k",), "value")

    cache.clear()

    assert cache.get(("k",)) is MISS
    assert len(cache) == 0
