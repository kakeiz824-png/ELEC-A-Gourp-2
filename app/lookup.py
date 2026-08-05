"""Title and author to book-metadata lookup.

The rest of the application searches through ``search_book(title)``,
``search_author(author)``, and ``lookup(title)``.  Behind them sit three
backends:

* ``mcp`` (the default) queries Open Library through the local MCP tool.
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
from app.details import BookDetails, cover_url_by_isbn, normalise, normalise_isbn


__all__ = [
    "BookDetails",
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


def search_seed(title: str) -> list[BookDetails]:
    """Return every seeded candidate for a title, best match first."""
    return _ranked(title, lambda candidate: candidate.title)


def search_seed_author(author: str) -> list[BookDetails]:
    """Return every seeded book written by an author, best match first."""
    return _ranked(author, lambda candidate: candidate.author)


def _search(
    query: str,
    *,
    kind: str,
    seed: Callable[[str], list[BookDetails]],
    direct: Callable[[str], list[BookDetails]],
    tool: Callable[[str], list[BookDetails]],
) -> list[BookDetails]:
    """Search the active backend, degrading to the seed, best match first.

    The title and author searches share one fallback policy: on either live
    backend an outage or an empty result falls through to the seed, so the books
    the demo relies on resolve either way.
    """
    backend = active_backend()
    if backend == SEED_BACKEND:
        return seed(query)

    if backend == OPENLIBRARY_BACKEND:
        try:
            results = direct(query)
        except openlibrary.LookupUnavailable:
            logger.warning(
                "Open Library unavailable for %s %r; using the seed", kind, query
            )
            return seed(query)
    else:
        try:
            results = tool(query)
        except mcp_client.MCPUnavailable:
            logger.warning(
                "MCP lookup unavailable for %s %r; using the seed", kind, query
            )
            return seed(query)

    return results or seed(query)


def search_book(title: str) -> list[BookDetails]:
    """Search the active backend for a title, best match first."""
    return _search(
        title,
        kind="title",
        seed=search_seed,
        direct=openlibrary.search_book,
        tool=mcp_client.search_book,
    )


def search_author(author: str) -> list[BookDetails]:
    """Search the active backend for books by an author, best match first."""
    return _search(
        author,
        kind="author",
        seed=search_seed_author,
        direct=openlibrary.search_author,
        tool=mcp_client.search_by_author,
    )


def lookup(title: str) -> BookDetails | None:
    """Return the best ISBN-bearing match for a title, or ``None``."""
    candidates = search_book(title)
    return next(
        (candidate for candidate in candidates if normalise_isbn(candidate.isbn)),
        None,
    )
