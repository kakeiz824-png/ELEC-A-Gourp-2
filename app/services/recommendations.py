"""Content-based recommendations: unread books in the reader's most-read categories.

The reader's own library is the only signal. Every book they finished or are
reading is looked at for the broad categories it was filed under (the same
categories auto-applied on add, matched case-insensitively so a hand-typed one
still counts). The categories are ranked, the catalogue is asked for other books
under the top few, and anything the reader already tracks is removed. This is
content-based, not collaborative: it never looks at another user's shelves.

Everything degrades to an empty list -- a new library, a library with only
free-form tags, or an offline catalogue all yield no suggestions rather than an
error, so the recommendations strip simply stays hidden.
"""

import sqlite3

from app.details import normalise_isbn
from app.lookup import books_in_category
from app.openlibrary import CATEGORY_KEYWORDS


# Only a tag that names one of our broad categories drives recommendations; a
# free-form tag like "2026" or "loaned to Sam" says nothing about subject.
KNOWN_CATEGORIES = tuple(CATEGORY_KEYWORDS)

# A finished book is a stronger taste signal than one still being read; a
# wishlist book has not been read at all, so it is left out entirely.
SHELF_WEIGHTS = {"finished": 2, "reading": 1}

DEFAULT_LIMIT = 10
# How many of the reader's top categories to draw from, and how many candidates
# to pull from each. A handful of categories keeps the strip coherent, and
# over-fetching per category leaves room after owned books are removed.
MAX_CATEGORIES = 3
PER_CATEGORY_FETCH = 12


def _canonical_category(name: str) -> str | None:
    """The known category a tag names, case-insensitively, or ``None``."""
    folded = name.casefold()
    for category in KNOWN_CATEGORIES:
        if category.casefold() == folded:
            return category
    return None


def _ranked_categories(
    connection: sqlite3.Connection, user_id: int
) -> list[str]:
    """The reader's categories, most-read first, from finished and reading books."""
    rows = connection.execute(
        """
        SELECT b.shelf AS shelf, t.name AS name
        FROM books b
        JOIN book_tags bt ON bt.book_id = b.id
        JOIN tags t ON t.id = bt.tag_id
        WHERE b.user_id = ? AND b.shelf IN ('finished', 'reading')
        """,
        (user_id,),
    ).fetchall()

    weights: dict[str, int] = {}
    for row in rows:
        category = _canonical_category(row["name"])
        if category is None:
            continue
        weights[category] = weights.get(category, 0) + SHELF_WEIGHTS[row["shelf"]]

    # Heaviest weight first, ties broken by name so the order is deterministic.
    return sorted(weights, key=lambda category: (-weights[category], category))[
        :MAX_CATEGORIES
    ]


def _owned_isbns(connection: sqlite3.Connection, user_id: int) -> set[str]:
    """Normalised ISBNs the reader already tracks, to exclude from suggestions."""
    rows = connection.execute(
        "SELECT isbn FROM books WHERE user_id = ?", (user_id,)
    ).fetchall()
    owned: set[str] = set()
    for row in rows:
        key = normalise_isbn(row["isbn"])
        if key:
            owned.add(key)
    return owned


def recommend(
    connection: sqlite3.Connection, user_id: int, *, limit: int = DEFAULT_LIMIT
) -> list[dict]:
    """Suggest unread books in the categories the reader reads most.

    Candidates from each top category are gathered in rank order, dropping any
    the reader owns and any already picked for an earlier category, then
    round-robined across the categories so the strongest categories are
    represented before any one fills the strip.
    """
    ranked = _ranked_categories(connection, user_id)
    if not ranked:
        return []

    owned = _owned_isbns(connection, user_id)
    seen: set[str] = set()
    by_category: dict[str, list[dict]] = {}

    for category in ranked:
        picks: list[dict] = []
        for details in books_in_category(category, limit=PER_CATEGORY_FETCH):
            key = normalise_isbn(details.isbn)
            if key is None or key in owned or key in seen:
                continue
            seen.add(key)
            picks.append(
                {
                    "title": details.title,
                    "author": details.author,
                    "isbn": details.isbn,
                    "cover_url": details.cover_url,
                    "year": details.year,
                    "category": category,
                }
            )
        by_category[category] = picks

    recommendations: list[dict] = []
    depth = 0
    while len(recommendations) < limit:
        added = False
        for category in ranked:
            picks = by_category[category]
            if depth < len(picks):
                recommendations.append(picks[depth])
                added = True
                if len(recommendations) >= limit:
                    break
        if not added:
            break
        depth += 1
    return recommendations
