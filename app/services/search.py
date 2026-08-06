"""Turning one catalogue search into the page of candidates the user picks from.

The search box is paired with a Title/Author selector, so this module is never
asked to guess which kind of thing was typed. Guessing was tried and removed: no
rule separates "Dune" the novel from Linda Dune the author, or "Harry Potter" the
series from Harry Potter the legal historian, because in every such pair both
readings are real books by real people. The selector costs one click and removes
the whole class of problem, and it halves the catalogue traffic that running both
searches required.

Results are paged rather than capped at a handful, because an author worth
searching for has written more than fits on one screen: Open Library lists over
four hundred results for J. K. Rowling.

Only ISBN-bearing candidates survive, because a book cannot be stored without an
ISBN.
"""

import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from math import ceil

from app.details import BookDetails, SearchPage, normalise_isbn
from app.lookup import search_author, search_book


logger = logging.getLogger(__name__)

DEFAULT_PER_PAGE = 10
MAX_PER_PAGE = 50


@dataclass(frozen=True)
class CandidatePage:
    """One page of selectable candidates, and where it sits in the results.

    ``total`` is the catalogue's count for the whole query, so ``pages`` is only
    as accurate as that count. Candidates without an ISBN are dropped after the
    page is fetched, so a page can hold fewer than ``per_page`` books while later
    pages still exist.
    """

    candidates: list[BookDetails]
    page: int
    per_page: int
    total: int

    @property
    def pages(self) -> int:
        """How many pages the whole result set spans, at least one."""
        return max(1, ceil(self.total / self.per_page)) if self.per_page else 1


def _distinct(results: Iterable[BookDetails]) -> list[BookDetails]:
    """Results that carry an ISBN, each ISBN kept once, normalised.

    The ISBN is normalised here so the value the browser sends back to
    ``POST /books`` is already the identity the database compares on.

    De-duplication is within a page: remembering every ISBN ever served would
    make the contents of page 3 depend on whether page 2 had been visited, and a
    stable page 3 matters more than never repeating an edition.
    """
    kept: list[BookDetails] = []
    seen: set[str] = set()
    for details in results:
        isbn = normalise_isbn(details.isbn)
        if isbn is None or isbn in seen:
            continue
        seen.add(isbn)
        kept.append(
            BookDetails(
                title=details.title,
                author=details.author,
                isbn=isbn,
                cover_url=details.cover_url,
                year=details.year,
            )
        )
    return kept


def _page(
    search: Callable[..., SearchPage],
    query: str,
    kind: str,
    page: int,
    per_page: int,
) -> CandidatePage:
    """Fetch one page, treating a backend failure as an empty result.

    A catalogue problem must not reach the browser as a 500; an empty page is a
    truthful answer to "what can I offer you".
    """
    try:
        found = search(query, limit=per_page, offset=(page - 1) * per_page)
    except Exception:
        logger.warning("%s search failed for %r", kind, query, exc_info=True)
        found = SearchPage(results=[], total=0)

    return CandidatePage(
        candidates=_distinct(found.results),
        page=page,
        per_page=per_page,
        total=found.total,
    )


def by_title(
    title: str, *, page: int = 1, per_page: int = DEFAULT_PER_PAGE
) -> CandidatePage:
    """One page of candidates whose title matches."""
    return _page(search_book, title, "Title", page, per_page)


def by_author(
    author: str, *, page: int = 1, per_page: int = DEFAULT_PER_PAGE
) -> CandidatePage:
    """One page of candidates written by an author."""
    return _page(search_author, author, "Author", page, per_page)
