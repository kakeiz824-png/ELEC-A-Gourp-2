"""Title and author to book-metadata lookup.

The rest of the application searches through ``search_book(title)`` and
``search_author(author)``, resolves one ISBN through ``details_for_isbn(isbn)``,
and keeps ``lookup(title)`` for the pre-search API contract.  Behind them sit
three backends:

* ``mcp`` (the default) queries Open Library through the local MCP tools.
* ``openlibrary`` keeps the direct HTTP path available for focused diagnostics.
* ``seed`` answers from ``seed/books.json`` alone, with no network at all.

``SHELF_LIFE_LOOKUP_BACKEND`` chooses between them.  The seed is not only the
offline demo: it is also the fallback whenever Open Library is unreachable or
has nothing for a query, so a network outage degrades the lookup instead of
breaking it.

``lookup`` returns ``None`` when neither backend matches.  The caller stores the
typed title with ``details_pending`` set, so a failed lookup is never a failed
add.
"""

import json
import logging
import os
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path

from app import mcp_client, openlibrary
from app.cache import MISS, TTLCache
from app.details import (
    AuthorDetails,
    BookDetails,
    SearchPage,
    cover_url_by_isbn,
    normalise,
    normalise_isbn,
)


__all__ = [
    "AuthorDetails",
    "BookDetails",
    "SearchPage",
    "author_profile",
    "books_in_category",
    "details_for_isbn",
    "lookup",
    "normalise",
    "search_author",
    "search_book",
    "search_seed",
    "search_seed_author",
]

logger = logging.getLogger(__name__)

SEED_PATH = Path(__file__).resolve().parent.parent / "seed" / "books.json"

BACKEND_ENV = "SHELF_LIFE_LOOKUP_BACKEND"
SEED_BACKEND = "seed"
MCP_BACKEND = "mcp"
OPENLIBRARY_BACKEND = "openlibrary"
DEFAULT_BACKEND = MCP_BACKEND

DEFAULT_LIMIT = 5

# Every cache key here starts with the active backend, so a test or demo that
# switches backends never reads a result another backend fetched.
_lookup_cache = TTLCache()


def clear_lookup_cache() -> None:
    """Drop every cached live-lookup answer (test isolation, diagnostics)."""
    _lookup_cache.clear()


def active_backend() -> str:
    """Which backend is in use.

    Read from the environment on every call, like ``db.get_db_path``, so a test
    or a demo can switch backends without reimporting anything.
    """
    configured = os.environ.get(BACKEND_ENV, DEFAULT_BACKEND).strip().lower()
    if configured not in (SEED_BACKEND, MCP_BACKEND, OPENLIBRARY_BACKEND):
        logger.warning(
            "Unknown %s=%r; falling back to %r", BACKEND_ENV, configured, DEFAULT_BACKEND
        )
        return DEFAULT_BACKEND
    return configured


@lru_cache(maxsize=1)
def _seed_catalogue() -> list[BookDetails]:
    raw = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    return [
        BookDetails(
            title=entry["title"],
            author=entry["author"],
            isbn=entry["isbn"],
            year=entry["year"],
            cover_url=cover_url_by_isbn(entry["isbn"]),
        )
        for entry in raw
    ]


def _ranked(query: str, field: Callable[[BookDetails], str | None]) -> list[BookDetails]:
    """Seeded books whose chosen field matches the query, best match first.

    An exact normalised match wins outright.  Otherwise a candidate matches when
    the query is a prefix of the field, then when the query appears anywhere in
    it, so "hobbit" finds its book and "tolkien" finds everything he wrote.
    """
    normalised_query = normalise(query)
    if not normalised_query:
        return []

    exact: list[BookDetails] = []
    prefix: list[BookDetails] = []
    contains: list[BookDetails] = []

    for candidate in _seed_catalogue():
        value = field(candidate)
        if value is None:
            continue
        normalised = normalise(value)
        if normalised == normalised_query:
            exact.append(candidate)
        elif normalised.startswith(normalised_query):
            prefix.append(candidate)
        elif normalised_query in normalised:
            contains.append(candidate)

    return exact + prefix + contains


def _seed_page(matches: list[BookDetails], limit: int, offset: int) -> SearchPage:
    """Slice seeded matches the same way a catalogue page is sliced."""
    return SearchPage(results=matches[offset : offset + limit], total=len(matches))


def search_seed(
    title: str, *, limit: int = DEFAULT_LIMIT, offset: int = 0
) -> SearchPage:
    """Return one page of seeded candidates for a title, best match first."""
    return _seed_page(_ranked(title, lambda candidate: candidate.title), limit, offset)


def search_seed_author(
    author: str, *, limit: int = DEFAULT_LIMIT, offset: int = 0
) -> SearchPage:
    """Return one page of seeded books written by an author, best match first."""
    return _seed_page(_ranked(author, lambda candidate: candidate.author), limit, offset)


def _search(
    query: str,
    *,
    kind: str,
    seed: Callable[..., SearchPage],
    direct: Callable[..., SearchPage],
    tool: Callable[..., SearchPage],
    limit: int,
    offset: int,
) -> SearchPage:
    """Search the active backend for one page, degrading to the seed.

    The title and author searches share one fallback policy: on either live
    backend an outage falls through to the seed, as does a catalogue that has
    never heard of the query.

    An empty page is *not* on its own a reason to fall back. Past the last page
    of a real result set every page is empty, and answering those with seeded
    books would put The Hobbit on page five of a search for something else. Only
    a reported total of zero means the catalogue truly has nothing.

    Only a genuine live result is cached. A seed fallback -- served when the live
    backend is unreachable or times out -- is deliberately *not* cached, because
    it is usually a transient outage: caching the tiny seed answer would pin a
    misleading result (e.g. a single seeded book for "J. K. Rowling") for the
    whole TTL even after the catalogue recovers.
    """
    backend = active_backend()
    if backend == SEED_BACKEND:
        return seed(query, limit=limit, offset=offset)

    cache_key = (backend, kind, normalise(query), limit, offset)
    cached = _lookup_cache.get(cache_key)
    if cached is not MISS:
        assert isinstance(cached, SearchPage)
        return cached

    if backend == OPENLIBRARY_BACKEND:
        try:
            page = direct(query, limit=limit, offset=offset)
        except openlibrary.LookupUnavailable:
            logger.warning("%s lookup unavailable; using the seed", kind)
            return seed(query, limit=limit, offset=offset)
    else:
        try:
            page = tool(query, limit=limit, offset=offset)
        except mcp_client.MCPUnavailable:
            logger.warning("%s lookup unavailable; using the seed", kind)
            return seed(query, limit=limit, offset=offset)

    if page.total == 0:
        # The catalogue genuinely has nothing; the seed may still answer, but
        # that fallback is not cached either, so a later live hit can replace it.
        return seed(query, limit=limit, offset=offset)

    _lookup_cache.set(cache_key, page)
    return page


def search_book(
    title: str, *, limit: int = DEFAULT_LIMIT, offset: int = 0
) -> SearchPage:
    """Search the active backend for a title, best match first."""
    return _search(
        title,
        kind="title",
        seed=search_seed,
        direct=openlibrary.search_book,
        tool=mcp_client.search_book,
        limit=limit,
        offset=offset,
    )


def search_author(
    author: str, *, limit: int = DEFAULT_LIMIT, offset: int = 0
) -> SearchPage:
    """Search the active backend for books by an author, best match first."""
    return _search(
        author,
        kind="author",
        seed=search_seed_author,
        direct=openlibrary.search_author,
        tool=mcp_client.search_author,
        limit=limit,
        offset=offset,
    )


def _seed_isbn(isbn: str) -> BookDetails | None:
    """The seeded book carrying an ISBN, comparing normalised forms."""
    key = normalise_isbn(isbn)
    if key is None:
        return None
    return next(
        (
            candidate
            for candidate in _seed_catalogue()
            if normalise_isbn(candidate.isbn) == key
        ),
        None,
    )


def details_for_isbn(isbn: str) -> BookDetails | None:
    """The catalogue record for one ISBN, or ``None`` if nothing carries it.

    This is how an addition is confirmed. An ISBN identifies a book, so asking
    the catalogue about it is both a check that the book is real and the source
    of its metadata, and nothing a client submitted has to be trusted.
    """
    backend = active_backend()
    if backend == SEED_BACKEND:
        return _seed_isbn(isbn)

    cache_key = (backend, "isbn", normalise_isbn(isbn) or isbn.strip().lower())

    def fetch() -> BookDetails | None:
        if backend == OPENLIBRARY_BACKEND:
            try:
                details = openlibrary.get_book_details(isbn)
            except openlibrary.LookupUnavailable:
                logger.warning(
                    "ISBN lookup unavailable; using the seed"
                )
                return _seed_isbn(isbn)
        else:
            try:
                details = mcp_client.get_book_details(isbn)
            except mcp_client.MCPUnavailable:
                logger.warning("ISBN lookup unavailable; using the seed")
                return _seed_isbn(isbn)
        return details or _seed_isbn(isbn)

    value = _lookup_cache.get_or_compute(cache_key, fetch)
    assert value is None or isinstance(value, BookDetails)
    return value


def author_profile(name: str) -> AuthorDetails | None:
    """The catalogue's profile for an author, or ``None`` when there is none.

    This backs the author page's biography panel. It is best-effort: the seed
    carries no biographies, so the seed backend and every live-backend outage
    answer ``None``, and the author's books still list around a missing profile
    rather than the whole search failing.
    """
    backend = active_backend()
    if backend == SEED_BACKEND:
        return None

    cache_key = (backend, "author_profile", normalise(name))

    def fetch() -> AuthorDetails | None:
        if backend == OPENLIBRARY_BACKEND:
            try:
                return openlibrary.get_author_details(name)
            except openlibrary.LookupUnavailable:
                logger.warning(
                    "author profile lookup unavailable"
                )
                return None
        try:
            return mcp_client.get_author_details(name)
        except mcp_client.MCPUnavailable:
            logger.warning("author profile lookup unavailable")
            return None

    value = _lookup_cache.get_or_compute(cache_key, fetch, cache_none=False)
    assert value is None or isinstance(value, AuthorDetails)
    return value


def tag_suggestions(isbn: str) -> list[str]:
    """Broad category suggestions for one ISBN, best-effort.

    Raw Open Library subjects are mapped into a small set of big categories so
    the tag editor offers a handful of clear choices. The seed catalogue
    carries no subjects and the MCP tools do not expose them, so this
    enrichment talks to the direct Open Library client only. A missing or slow
    catalogue yields an empty list, never an error.
    """
    if active_backend() == SEED_BACKEND:
        return []
    return openlibrary.suggest_categories(openlibrary.subjects_for_isbn(isbn))


def books_in_category(category: str, *, limit: int = DEFAULT_LIMIT) -> list[BookDetails]:
    """Live catalogue books filed under a broad category, best-effort.

    This backs recommendations. Like ``tag_suggestions`` it talks to the direct
    Open Library client regardless of the active backend, because the seed
    carries no subjects and the MCP tools do not expose a subject search; the
    seed backend and any catalogue outage answer with an empty list rather than
    an error. Only ISBN-bearing results are returned, since a book with no ISBN
    cannot be added. A genuine answer is cached for the usual TTL so a page of
    recommendations does not re-query the same categories on every refresh.
    """
    if active_backend() == SEED_BACKEND:
        return []
    subject = openlibrary.CATEGORY_SUBJECT_QUERY.get(category)
    if subject is None:
        return []

    cache_key = (active_backend(), "category", normalise(category), limit)

    def fetch() -> list[BookDetails]:
        try:
            page = openlibrary.search_by_subject(subject, limit=limit)
        except openlibrary.LookupUnavailable:
            logger.warning("category lookup unavailable for %r", category)
            return []
        return [details for details in page.results if normalise_isbn(details.isbn)]

    # An empty list is cached like any other answer. That briefly pins an
    # outage-driven empty for the TTL, but recommendations are a bonus strip, not
    # a search result, so a few minutes without them after a blip is acceptable
    # -- and caching spares the catalogue a fan-out of subject queries on every
    # shelf refresh.
    value = _lookup_cache.get_or_compute(cache_key, fetch)
    assert isinstance(value, list)
    return value


def lookup(title: str) -> BookDetails | None:
    """Return the best ISBN-bearing match for a title, or ``None``.

    Kept for ``POST /books`` without an ISBN, the contract that existed before
    the search UI: the caller names a book and the catalogue picks the edition.
    """
    page = search_book(title)
    return next(
        (
            candidate
            for candidate in page.results
            if normalise_isbn(candidate.isbn)
        ),
        None,
    )
