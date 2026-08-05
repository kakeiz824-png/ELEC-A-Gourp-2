"""Turning catalogue searches into the candidates the user chooses between.

The search box holds one string and the caller cannot know whether it is a title
or an author's name, so ``by_query`` runs both searches and interleaves them.  A
title match always takes the first slot, which keeps "The Hobbit" ranking exactly
as it did, and an author match is guaranteed the second, so "George Orwell"
surfaces Nineteen Eighty-Four instead of five biographies and study guides whose
titles merely contain his name.

Interleaving rather than concatenating matters because the list is capped: an
author name is usually also a weak title match, so title results alone would fill
every slot and the author's own books would never be seen.

A guaranteed slot has to be earned, though, because plenty of people share a
surname with a famous book.  Searching "Dune" finds authors named Dune, and their
books are not what the person typing it wants.  So an author result is only
interleaved when the query names that author in full; a result that matched only
part of a name is appended, and therefore appears only if the title results left
room.

Only ISBN-bearing candidates survive, because a book cannot be stored without an
ISBN, and each ISBN is offered once however many searches found it.
"""

import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from itertools import zip_longest

from app.details import BookDetails, normalise, normalise_isbn
from app.lookup import search_author, search_book


logger = logging.getLogger(__name__)

MAX_CANDIDATES = 5

TITLE_MATCH = "title"
AUTHOR_MATCH = "author"


@dataclass(frozen=True)
class Candidate:
    """One selectable search result, and which search turned it up."""

    details: BookDetails
    matched: str


def _found(
    search: Callable[[str], list[BookDetails]],
    query: str,
    matched: str,
) -> list[Candidate]:
    """Run one search and label its results, treating failure as no results.

    A backend problem must not reach the browser as a 500: the other search may
    still have something, and an empty list is a truthful answer to "what can I
    offer you".
    """
    try:
        results = search(query)
    except Exception:
        logger.warning("%s search failed for %r", matched, query, exc_info=True)
        return []
    return [Candidate(details=details, matched=matched) for details in results]


def _significant(name: str) -> set[str]:
    """The tokens of a name that carry identity; a single letter is an initial."""
    return {token for token in normalise(name).split() if len(token) > 1}


def _squashed(name: str) -> str:
    """A name with its spacing removed, so "J. R. R." meets "J.R.R." halfway."""
    return normalise(name).replace(" ", "")


def _names_the_whole_author(query: str, author: str | None) -> bool:
    """True when the query names this author in full rather than in part.

    Two ways to qualify.  The names can be the same once spacing is ignored,
    which is what lets "J. R. R. Tolkien" meet the catalogue's "J.R.R. Tolkien".
    Or every identifying token of the author's name can appear in the query, so
    "Ursula Le Guin" still names Ursula K. Le Guin.

    "Dune" qualifies as neither for Linda Dune, and "Tolkien" as neither for
    J.R.R. Tolkien: both name a real author, but only partly, and a partial name
    is too weak a signal to spend a guaranteed slot on.
    """
    if author is None:
        return False
    if _squashed(query) == _squashed(author):
        return True
    author_tokens = _significant(author)
    return bool(author_tokens) and author_tokens <= _significant(query)


def _interleave(
    first: list[Candidate], second: list[Candidate]
) -> list[Candidate]:
    """One candidate from each list in turn, starting with the first."""
    merged: list[Candidate] = []
    for pair in zip_longest(first, second):
        merged.extend(candidate for candidate in pair if candidate is not None)
    return merged


def _selectable(candidates: Iterable[Candidate]) -> list[Candidate]:
    """Up to five candidates that have an ISBN, each ISBN kept once.

    The kept ISBN is the normalised one, so the value the browser sends back to
    ``POST /books`` is already the identity the database compares on.  First
    occurrence wins, so a book found by both searches is labelled by whichever
    search ranked it sooner.
    """
    kept: list[Candidate] = []
    seen: set[str] = set()
    for candidate in candidates:
        isbn = normalise_isbn(candidate.details.isbn)
        if isbn is None or isbn in seen:
            continue
        seen.add(isbn)
        kept.append(
            Candidate(
                details=BookDetails(
                    title=candidate.details.title,
                    author=candidate.details.author,
                    isbn=isbn,
                    cover_url=candidate.details.cover_url,
                    year=candidate.details.year,
                ),
                matched=candidate.matched,
            )
        )
        if len(kept) == MAX_CANDIDATES:
            break
    return kept


def by_title(title: str) -> list[Candidate]:
    """Selectable candidates whose title matches."""
    return _selectable(_found(search_book, title, TITLE_MATCH))


def by_author(author: str) -> list[Candidate]:
    """Selectable candidates written by an author."""
    return _selectable(_found(search_author, author, AUTHOR_MATCH))


def by_query(query: str) -> list[Candidate]:
    """Selectable candidates for a search box that may hold either.

    Both searches run, so this costs two catalogue calls rather than one.  That
    is the price of not asking the user to say which kind of thing they typed.
    """
    titles = _found(search_book, query, TITLE_MATCH)

    named: list[Candidate] = []
    partial: list[Candidate] = []
    for candidate in _found(search_author, query, AUTHOR_MATCH):
        if _names_the_whole_author(query, candidate.details.author):
            named.append(candidate)
        else:
            partial.append(candidate)

    return _selectable(_interleave(titles, named) + partial)
