"""The value type every lookup backend returns.

Both lookup backends -- the seeded table and the live Open Library client --
produce a ``BookDetails``, so it lives here rather than in either of them and
neither has to import the other.

Only ``title`` is guaranteed.  A real catalogue record is often missing an
author, a year, an ISBN, or a cover, and the ``books`` table holds NULL for all
four, so the optional fields say so rather than inventing a placeholder.
"""

import re
from dataclasses import dataclass


COVER_URL_BY_ISBN = "https://covers.openlibrary.org/b/isbn/{isbn}-M.jpg"
COVER_URL_BY_ID = "https://covers.openlibrary.org/b/id/{cover_id}-M.jpg"
AUTHOR_PHOTO_URL_BY_ID = "https://covers.openlibrary.org/a/id/{photo_id}-M.jpg"


@dataclass(frozen=True)
class BookDetails:
    """One lookup result, whichever backend produced it."""

    title: str
    author: str | None = None
    isbn: str | None = None
    year: int | None = None
    cover_url: str | None = None


@dataclass(frozen=True)
class AuthorDetails:
    """One author profile, whichever backend produced it.

    Only ``name`` is guaranteed.  Open Library often has no biography, no dates,
    and no photo for an author, so every other field is optional and says so
    rather than inventing a placeholder -- exactly like ``BookDetails``.
    """

    name: str
    bio: str | None = None
    birth_date: str | None = None
    death_date: str | None = None
    work_count: int | None = None
    photo_url: str | None = None


@dataclass(frozen=True)
class SearchPage:
    """One slice of a search, plus how many results it was cut from.

    ``total`` is what the catalogue reports for the whole query, not the length
    of ``results``, so a caller can say "page 3 of 43" without fetching the other
    42.  It counts what the catalogue matched: results lacking an ISBN are
    dropped later, so a page can be shorter than the slice that was asked for.
    """

    results: list[BookDetails]
    total: int

    @property
    def empty(self) -> bool:
        return not self.results


def normalise(title: str) -> str:
    """Fold a title down to something two spellings of it can both reach."""
    lowered = title.strip().lower()
    without_punctuation = re.sub(r"[^\w\s]", "", lowered)
    return re.sub(r"\s+", " ", without_punctuation).strip()


def normalise_isbn(isbn: str | None) -> str | None:
    """Return an ISBN suitable for identity comparisons.

    Catalogue providers variously include spaces and hyphens. Those formatting
    differences do not make two ISBNs different, so keep only digits and a
    possible ISBN-10 check character.
    """
    if isbn is None:
        return None
    normalized = re.sub(r"[^0-9Xx]", "", isbn).upper()
    return normalized or None


def cover_url_by_isbn(isbn: str | None) -> str | None:
    """Cover for an ISBN, or ``None`` when there is no ISBN to ask about."""
    return COVER_URL_BY_ISBN.format(isbn=isbn) if isbn else None


def cover_url_by_id(cover_id: object) -> str | None:
    """Cover for an Open Library cover id, or ``None`` if it is not a number."""
    if isinstance(cover_id, bool) or not isinstance(cover_id, int):
        return None
    return COVER_URL_BY_ID.format(cover_id=cover_id)


def author_photo_url_by_id(photo_id: object) -> str | None:
    """Photo for an Open Library author id, or ``None`` when there is none.

    Author photo ids are positive integers; Open Library uses ``-1`` (and other
    non-positive values) to mean "no photo", so those map to ``None`` rather than
    to a URL that would resolve to a blank image.
    """
    if isinstance(photo_id, bool) or not isinstance(photo_id, int) or photo_id <= 0:
        return None
    return AUTHOR_PHOTO_URL_BY_ID.format(photo_id=photo_id)


def year_from(value: object) -> int | None:
    """Pull a four-digit year out of whatever the catalogue gave us.

    Open Library publication dates are free text: ``2011``, ``March 2011``,
    ``2011-03-01`` and ``c1937`` all occur.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if not isinstance(value, str):
        return None
    match = re.search(r"\b(\d{4})\b", value)
    return int(match.group(1)) if match else None
