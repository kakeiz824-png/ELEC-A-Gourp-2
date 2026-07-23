"""Title to book-metadata lookup.

The rest of the application depends only on ``lookup(title)``.  At M1 it is
backed by the seeded table in ``seed/books.json`` so the add-by-title path is
demoable with no network.  At M2 the body is swapped for the Open Library MCP
tools (``search_book`` / ``get_book_details``); this signature does not change,
so no caller has to change with it.

``lookup`` returns ``None`` when nothing matches.  The caller stores the typed
title with ``details_pending`` set, so a failed lookup is never a failed add.
"""

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


SEED_PATH = Path(__file__).resolve().parent.parent / "seed" / "books.json"
COVER_URL_TEMPLATE = "https://covers.openlibrary.org/b/isbn/{isbn}-M.jpg"


@dataclass(frozen=True)
class BookDetails:
    """One lookup result. Mirrors what ``search_book`` returns at M2."""

    title: str
    author: str
    isbn: str
    year: int
    cover_url: str


def normalise(title: str) -> str:
    """Fold a title down to something two spellings of it can both reach."""
    lowered = title.strip().lower()
    without_punctuation = re.sub(r"[^\w\s]", "", lowered)
    return re.sub(r"\s+", " ", without_punctuation).strip()


@lru_cache(maxsize=1)
def _seed_catalogue() -> list[BookDetails]:
    raw = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    return [
        BookDetails(
            title=entry["title"],
            author=entry["author"],
            isbn=entry["isbn"],
            year=entry["year"],
            cover_url=COVER_URL_TEMPLATE.format(isbn=entry["isbn"]),
        )
        for entry in raw
    ]


def search_book(title: str) -> list[BookDetails]:
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


def lookup(title: str) -> BookDetails | None:
    """Return the best match for a title, or ``None`` if there is none."""
    candidates = search_book(title)
    return candidates[0] if candidates else None
