"""A small bounded TTL cache, shared by the lookup and MCP layers.

Both layers talk to the same slow external catalogue and want the same thing
from a cache: repeat questions answered without a second network round-trip, a
short lifetime so metadata does not go stale, and a bound so a long-running
process cannot grow without limit. That is one behaviour, so it lives here once
rather than being written twice.

Nothing here knows what it is storing. The lookup module keys its entries by
backend so a result fetched by one backend is never served to another, and the
MCP server keys its own by tool; those are each caller's concern.

Eviction is deliberately crude: at capacity the whole cache is dropped rather
than the least-recently-used entry evicted. The entries are cheap to recompute
and the bound exists to cap memory, not to maximise hit rate, so tracking usage
order would cost more than it saves.
"""

from collections.abc import Callable
from time import monotonic


DEFAULT_TTL_SECONDS = 300.0
DEFAULT_MAX_ENTRIES = 256


class _Missing:
    """Sentinel distinguishing "not cached" from a cached ``None``."""


MISS = _Missing()


class TTLCache:
    """Values kept for ``ttl_seconds``, discarded wholesale at ``max_entries``."""

    __slots__ = ("_entries", "_max_entries", "_ttl")

    def __init__(
        self,
        *,
        ttl_seconds: float = DEFAULT_TTL_SECONDS,
        max_entries: int = DEFAULT_MAX_ENTRIES,
    ) -> None:
        self._ttl = ttl_seconds
        self._max_entries = max_entries
        self._entries: dict[tuple, tuple[float, object]] = {}

    def get(self, key: tuple) -> object:
        """The live value for ``key``, or :data:`MISS` when absent or expired.

        ``MISS`` rather than ``None`` is returned for a miss so a caller that
        legitimately caches ``None`` can tell the two apart.
        """
        entry = self._entries.get(key)
        if entry is None:
            return MISS
        stored_at, value = entry
        if monotonic() - stored_at >= self._ttl:
            return MISS
        return value

    def set(self, key: tuple, value: object) -> None:
        """Store ``value``, clearing the cache first if it is at capacity."""
        if len(self._entries) >= self._max_entries and key not in self._entries:
            self._entries.clear()
        self._entries[key] = (monotonic(), value)

    def get_or_compute(
        self, key: tuple, compute: Callable[[], object], *, cache_none: bool = True
    ) -> object:
        """Return the cached value for ``key``, computing and storing on a miss.

        ``compute`` is called only on a miss, and an exception it raises
        propagates without being stored, so a failure is retried rather than
        pinned for the whole TTL.

        ``cache_none=False`` skips storing a ``None`` result. A lookup that came
        back empty is sometimes a transient timeout on a slow catalogue rather
        than a settled "there is no such thing"; caching that would make one slow
        moment stick, while recomputing on the next call is cheap and lets a
        recovered catalogue answer straight away.
        """
        cached = self.get(key)
        if cached is not MISS:
            return cached

        value = compute()
        if value is None and not cache_none:
            return None
        self.set(key, value)
        return value

    def clear(self) -> None:
        """Drop every entry (test isolation, diagnostics)."""
        self._entries.clear()

    def __len__(self) -> int:
        return len(self._entries)
