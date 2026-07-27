"""Title to book-metadata lookup.

The rest of the application depends only on ``lookup(title)``.  Behind it sit
two backends:

* ``openlibrary`` (the default) queries the live Open Library catalogue.
* ``seed`` answers from ``seed/books.json`` alone, with no network at all.

``SHELF_LIFE_LOOKUP_BACKEND`` chooses between them.  The seed is not only the
offline demo: it is also the fallback whenever Open Library is unreachable or
has nothing for a title, so a network outage degrades the lookup instead of
breaking it.

``lookup`` returns ``None`` when neither backend matches.  The caller stores the
typed title with ``details_pending`` set, so a failed lookup is never a failed
add.
"""

import json
import logging
import os
from functools import lru_cache
from pathlib import Path

from app import openlibrary
from app.details import BookDetails, cover_url_by_isbn, normalise


__all__ = ["BookDetails", "lookup", "normalise", "search_book", "search_seed"]

logger = logging.getLogger(__name__)

SEED_PATH = Path(__file__).resolve().parent.parent / "seed" / "books.json"

BACKEND_ENV = "SHELF_LIFE_LOOKUP_BACKEND"
SEED_BACKEND = "seed"
OPENLIBRARY_BACKEND = "openlibrary"
DEFAULT_BACKEND = OPENLIBRARY_BACKEND


def active_backend() -> str:
    """Which backend is in use.

    Read from the environment on every call, like ``db.get_db_path``, so a test
    or a demo can switch backends without reimporting anything.
    """
    configured = os.environ.get(BACKEND_ENV, DEFAULT_BACKEND).strip().lower()
    if configured not in (SEED_BACKEND, OPENLIBRARY_BACKEND):
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


def search_seed(title: str) -> list[BookDetails]:
    """Return every seeded candidate for a title, best match first.

    An exact normalised match wins outright.  Otherwise a candidate matches when
    the query is a prefix of its title, then when the query appears anywhere in
    it, so "hobbit" and "sapiens" both find their book.
    """
    query = normalise(title)
    if not query:
        return []

    exact: list[BookDetails] = []
    prefix: list[BookDetails] = []
    contains: list[BookDetails] = []

    for candidate in _seed_catalogue():
        normalised = normalise(candidate.title)
        if normalised == query:
            exact.append(candidate)
        elif normalised.startswith(query):
            prefix.append(candidate)
        elif query in normalised:
            contains.append(candidate)

    return exact + prefix + contains


def search_book(title: str) -> list[BookDetails]:
    """Search the active backend for a title, best match first.

    On the Open Library backend an outage or an empty result falls through to
    the seed, so the titles the demo relies on resolve either way.
    """
    if active_backend() == SEED_BACKEND:
        return search_seed(title)

    try:
        results = openlibrary.search_book(title)
    except openlibrary.LookupUnavailable:
        logger.warning("Open Library unavailable for %r; using the seed", title)
        return search_seed(title)

    return results or search_seed(title)


def lookup(title: str) -> BookDetails | None:
    """Return the best match for a title, or ``None`` if there is none."""
    candidates = search_book(title)
    return candidates[0] if candidates else None
