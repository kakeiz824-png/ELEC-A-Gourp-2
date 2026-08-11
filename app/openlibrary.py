"""Open Library client: the external book database behind ``lookup``.

Open Library is keyless and public, so there is no credential to configure --
only a timeout, because a slow catalogue must not hold an add open.  Three calls
are wrapped:

* ``search_book(title)`` -- title search, best match first.
* ``search_author(author)`` -- books written by an author, best match first.
* ``get_book_details(isbn)`` -- the precise record for one ISBN.

Every network or protocol failure surfaces as ``LookupUnavailable`` so the
caller can tell "the catalogue is down" (fall back, retry later) apart from
"the catalogue has no such book" (an empty result).  Nothing here touches the
database or the API models: it maps catalogue JSON to ``BookDetails`` and stops.
"""

import logging
import os
from typing import Any

import httpx

from app.details import (
    AuthorDetails,
    BookDetails,
    SearchPage,
    author_photo_url_by_id,
    cover_url_by_id,
    cover_url_by_isbn,
    normalise,
    year_from,
)


logger = logging.getLogger(__name__)

SEARCH_URL = "https://openlibrary.org/search.json"
BOOKS_URL = "https://openlibrary.org/api/books"
AUTHORS_SEARCH_URL = "https://openlibrary.org/search/authors.json"
AUTHOR_URL = "https://openlibrary.org/authors/{key}.json"

# Asking for named fields keeps the response small: an unfiltered search doc
# carries hundreds of keys, including every edition ISBN.
SEARCH_FIELDS = "title,author_name,first_publish_year,isbn,cover_i"
AUTHOR_SEARCH_FIELDS = "key,name,birth_date,death_date,work_count"
SEARCH_LIMIT = 5

DEFAULT_TIMEOUT = 5.0
TIMEOUT_ENV = "SHELF_LIFE_OPENLIBRARY_TIMEOUT"

# Open Library asks unauthenticated clients to identify themselves.
HEADERS = {
    "User-Agent": "ShelfLife/0.2 (reading tracker; student project)",
    "Accept": "application/json",
}


class LookupUnavailable(RuntimeError):
    """The catalogue could not be reached or answered with something unusable."""


def timeout() -> float:
    """Request timeout in seconds, overridable per environment."""
    raw = os.environ.get(TIMEOUT_ENV, "")
    try:
        parsed = float(raw)
    except ValueError:
        return DEFAULT_TIMEOUT
    return parsed if parsed > 0 else DEFAULT_TIMEOUT


def client() -> httpx.Client:
    """Build the HTTP client.

    This is the seam the tests replace with a mock transport, so no test ever
    reaches the real Open Library.
    """
    return httpx.Client(headers=HEADERS, timeout=timeout(), follow_redirects=True)


def _get_json(url: str, params: dict[str, Any]) -> Any:
    """GET one JSON document, or raise ``LookupUnavailable``."""
    try:
        with client() as http:
            response = http.get(url, params=params)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as exc:
        raise LookupUnavailable(f"Open Library request failed: {exc}") from exc
    except ValueError as exc:  # includes JSONDecodeError
        raise LookupUnavailable(f"Open Library returned invalid JSON: {exc}") from exc


def _first_string(values: object) -> str | None:
    """First usable string in a catalogue list field."""
    if not isinstance(values, list):
        return None
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _preferred_isbn(values: object) -> str | None:
    """Pick one ISBN out of an edition list, preferring a 13-digit one.

    A search doc lists the ISBN of every edition, in no particular order.  The
    13-digit form is what covers and later ISBN lookups work best with.
    """
    if not isinstance(values, list):
        return None
    candidates = [value.strip() for value in values if isinstance(value, str) and value.strip()]
    for candidate in candidates:
        if len(candidate) == 13 and candidate.isdigit():
            return candidate
    return candidates[0] if candidates else None


def _doc_to_details(doc: object) -> BookDetails | None:
    """Map one search doc to ``BookDetails``, or drop it if it has no title."""
    if not isinstance(doc, dict):
        return None
    title = doc.get("title")
    if not isinstance(title, str) or not title.strip():
        return None

    isbn = _preferred_isbn(doc.get("isbn"))
    return BookDetails(
        title=title.strip(),
        author=_first_string(doc.get("author_name")),
        isbn=isbn,
        year=year_from(doc.get("first_publish_year")),
        cover_url=cover_url_by_id(doc.get("cover_i")) or cover_url_by_isbn(isbn),
    )


def _total(payload: dict, fallback: int) -> int:
    """How many results the catalogue says the whole query has."""
    found = payload.get("numFound")
    if isinstance(found, bool) or not isinstance(found, int) or found < 0:
        return fallback
    return found


def _docs(payload: object, label: str) -> tuple[list, int]:
    """The raw result docs and the reported total, or raise."""
    if not isinstance(payload, dict):
        raise LookupUnavailable(f"Open Library {label} did not return an object")
    docs = payload.get("docs")
    if not isinstance(docs, list):
        return [], 0
    return docs, _total(payload, len(docs))


def _details_page(docs: list, total: int) -> SearchPage:
    """Map result docs to a page, dropping any that have no title."""
    mapped = (_doc_to_details(doc) for doc in docs)
    return SearchPage(
        results=[details for details in mapped if details is not None], total=total
    )


def search_book(
    title: str, *, limit: int = SEARCH_LIMIT, offset: int = 0
) -> SearchPage:
    """Search Open Library by title, then fall back to its broad query.

    Open Library already returns its own relevance order, which is better than
    anything re-ranking here could do, so the order is left alone.
    """
    query = normalise(title)
    if not query:
        return SearchPage(results=[], total=0)

    docs, total = _docs(
        _get_json(
            SEARCH_URL,
            {
                "title": title.strip(),
                "limit": limit,
                "offset": offset,
                "fields": SEARCH_FIELDS,
            },
        ),
        "search",
    )
    if total == 0:
        # The title index knows nothing about this string, so try the broad
        # query, which also reads subjects and descriptions.  This is decided
        # from the reported total rather than from this page being empty, so
        # asking for page 5 of a broad-query search does not silently fall back
        # to the title index for every page past the end.
        docs, total = _docs(
            _get_json(
                SEARCH_URL,
                {
                    "q": title.strip(),
                    "limit": limit,
                    "offset": offset,
                    "fields": SEARCH_FIELDS,
                },
            ),
            "broad search",
        )

    return _details_page(docs, total)


def _author_tokens(author: str) -> list[str]:
    """The query tokens worth matching on.

    Single letters are dropped because an initial carries no signal: the query
    "J. R. R. Tolkien" must still match the catalogue's "J.R.R. Tolkien", whose
    initials fold into one token.
    """
    return [token for token in normalise(author).split() if len(token) > 1]


def _doc_is_by_author(doc: object, tokens: list[str]) -> bool:
    """True when the doc's primary author carries every query token.

    An ``author=`` search also returns anthologies and year's-best collections
    the author only contributed one story to, whose primary author is somebody
    else entirely.  Testing the primary author keeps the results to books the
    query is really about, and it keeps the author shown on the card -- also the
    primary one -- consistent with why the result was included.
    """
    if not isinstance(doc, dict):
        return False
    primary = _first_string(doc.get("author_name"))
    if primary is None:
        return False
    normalised = normalise(primary)
    return all(token in normalised for token in tokens)


def search_author(
    author: str, *, limit: int = SEARCH_LIMIT, offset: int = 0
) -> SearchPage:
    """Search Open Library for books written by an author, best match first.

    ``author=`` queries the catalogue's author index, so unlike a title search
    it returns the author's own works instead of biographies and study guides
    whose titles happen to contain their name.  Open Library's own relevance
    order is kept, as in ``search_book``.

    The relevance filter runs over one page, so ``total`` counts what the
    catalogue matched rather than what survives filtering.  A page can therefore
    be shorter than the one before it.
    """
    query = normalise(author)
    if not query:
        return SearchPage(results=[], total=0)

    docs, total = _docs(
        _get_json(
            SEARCH_URL,
            {
                "author": author.strip(),
                "limit": limit,
                "offset": offset,
                "fields": SEARCH_FIELDS,
            },
        ),
        "author search",
    )

    tokens = _author_tokens(author)
    if tokens:
        # Never let the relevance filter empty a page: an author credited only
        # as a co-author would otherwise vanish rather than rank low.
        docs = [doc for doc in docs if _doc_is_by_author(doc, tokens)] or docs

    return _details_page(docs, total)


def get_book_details(isbn: str) -> BookDetails | None:
    """Fetch the record for one ISBN, or ``None`` if the catalogue has none."""
    key = isbn.strip().replace("-", "").replace(" ", "")
    if not key:
        return None

    payload = _get_json(
        BOOKS_URL, {"bibkeys": f"ISBN:{key}", "format": "json", "jscmd": "data"}
    )
    if not isinstance(payload, dict):
        raise LookupUnavailable("Open Library books API did not return an object")

    record = payload.get(f"ISBN:{key}")
    if not isinstance(record, dict):
        return None

    title = record.get("title")
    if not isinstance(title, str) or not title.strip():
        return None

    authors = record.get("authors")
    author = None
    if isinstance(authors, list):
        author = _first_string(
            [entry.get("name") for entry in authors if isinstance(entry, dict)]
        )

    cover = record.get("cover")
    cover_url = cover.get("medium") if isinstance(cover, dict) else None
    if not isinstance(cover_url, str) or not cover_url.strip():
        cover_url = cover_url_by_isbn(key)

    return BookDetails(
        title=title.strip(),
        author=author,
        isbn=key,
        year=year_from(record.get("publish_date")),
        cover_url=cover_url,
    )


def _text(value: object) -> str | None:
    """A stripped non-empty string, or ``None`` for anything else."""
    return value.strip() if isinstance(value, str) and value.strip() else None


def _author_key(doc: object) -> str | None:
    """The bare OLID (e.g. ``OL23919A``) from a ``search/authors`` doc.

    The author search index returns the bare id, but the same field is a
    ``/authors/OL…A`` path elsewhere in Open Library, so the trailing segment is
    taken to accept either shape.
    """
    if not isinstance(doc, dict):
        return None
    key = _text(doc.get("key"))
    return key.rsplit("/", 1)[-1] if key else None


def _author_bio(value: object) -> str | None:
    """Pull a biography out of the two shapes Open Library uses.

    An author record carries ``bio`` either as a plain string or as a typed text
    object ``{"type": "/type/text", "value": "…"}``.
    """
    if isinstance(value, str):
        return _text(value)
    if isinstance(value, dict):
        return _text(value.get("value"))
    return None


def _work_count(value: object) -> int | None:
    """How many works the catalogue credits the author with, if it is a count."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _first_author_photo(photos: object) -> str | None:
    """The URL of the first usable author photo id, or ``None``."""
    if not isinstance(photos, list):
        return None
    for photo_id in photos:
        url = author_photo_url_by_id(photo_id)
        if url:
            return url
    return None


def get_author_details(name: str) -> AuthorDetails | None:
    """Fetch an author's profile by name, or ``None`` if none matches.

    Two calls: the author search index resolves a name to the best-matching
    author record -- its OLID, display name, dates, and work count -- and the
    author record itself supplies the biography and photo the search index
    omits.  A name that matches nobody yields ``None``; any network or protocol
    failure surfaces as ``LookupUnavailable`` so the caller can degrade to "no
    profile" instead of failing the author search around it.
    """
    query = normalise(name)
    if not query:
        return None

    docs, _ = _docs(
        _get_json(
            AUTHORS_SEARCH_URL,
            {"q": name.strip(), "limit": 1, "fields": AUTHOR_SEARCH_FIELDS},
        ),
        "author profile search",
    )
    doc = docs[0] if docs else None
    if not isinstance(doc, dict):
        return None

    record: dict = {}
    key = _author_key(doc)
    if key:
        fetched = _get_json(AUTHOR_URL.format(key=key), {})
        if isinstance(fetched, dict):
            record = fetched

    return AuthorDetails(
        name=_text(doc.get("name")) or _text(record.get("name")) or name.strip(),
        bio=_author_bio(record.get("bio")),
        birth_date=_text(record.get("birth_date")) or _text(doc.get("birth_date")),
        death_date=_text(record.get("death_date")) or _text(doc.get("death_date")),
        work_count=_work_count(doc.get("work_count")),
        photo_url=_first_author_photo(record.get("photos")),
    )
