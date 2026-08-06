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
from app.details import (
    BookDetails,
    SearchPage,
    cover_url_by_isbn,
    normalise,
    normalise_isbn,
)


__all__ = [
    "BookDetails",
    "SearchPage",
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
    """
    backend = active_backend()
    if backend == SEED_BACKEND:
        return seed(query, limit=limit, offset=offset)

    if backend == OPENLIBRARY_BACKEND:
        try:
            page = direct(query, limit=limit, offset=offset)
        except openlibrary.LookupUnavailable:
            logger.warning(
                "Open Library unavailable for %s %r; using the seed", kind, query
            )
            return seed(query, limit=limit, offset=offset)
    else:
        try:
            page = tool(query, limit=limit, offset=offset)
        except mcp_client.MCPUnavailable:
            logger.warning(
                "MCP lookup unavailable for %s %r; using the seed", kind, query
            )
            return seed(query, limit=limit, offset=offset)

    if page.total == 0:
        return seed(query, limit=limit, offset=offset)
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

    if backend == OPENLIBRARY_BACKEND:
        try:
            details = openlibrary.get_book_details(isbn)
        except openlibrary.LookupUnavailable:
            logger.warning("Open Library unavailable for ISBN %r; using the seed", isbn)
            return _seed_isbn(isbn)
    else:
        try:
            details = mcp_client.get_book_details(isbn)
        except mcp_client.MCPUnavailable:
            logger.warning("MCP lookup unavailable for ISBN %r; using the seed", isbn)
            return _seed_isbn(isbn)

    return details or _seed_isbn(isbn)


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
