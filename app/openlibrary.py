"""Open Library client: the external book database behind ``lookup``.

Open Library is keyless and public, so there is no credential to configure --
only a timeout, because a slow catalogue must not hold an add open.  Two calls
are wrapped, matching the two tools M2 specifies:

* ``search_book(title)`` -- title search, best match first.
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

from app.details import BookDetails, cover_url_by_id, cover_url_by_isbn, normalise, year_from


logger = logging.getLogger(__name__)

SEARCH_URL = "https://openlibrary.org/search.json"
BOOKS_URL = "https://openlibrary.org/api/books"

# Asking for named fields keeps the response small: an unfiltered search doc
# carries hundreds of keys, including every edition ISBN.
SEARCH_FIELDS = "title,author_name,first_publish_year,isbn,cover_i"
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


def search_book(title: str) -> list[BookDetails]:
    """Search Open Library by title, then fall back to its broad query.

    Open Library already returns its own relevance order, which is better than
    anything re-ranking here could do, so the order is left alone.
    """
    query = normalise(title)
    if not query:
        return []

    payload = _get_json(
        SEARCH_URL,
        {"title": title.strip(), "limit": SEARCH_LIMIT, "fields": SEARCH_FIELDS},
    )
    if not isinstance(payload, dict):
        raise LookupUnavailable("Open Library search did not return an object")

    docs = payload.get("docs")
    if not isinstance(docs, list):
        return []
    if not docs:
        payload = _get_json(
            SEARCH_URL,
            {"q": title.strip(), "limit": SEARCH_LIMIT, "fields": SEARCH_FIELDS},
        )
        if not isinstance(payload, dict):
            raise LookupUnavailable("Open Library broad search did not return an object")
        docs = payload.get("docs")
        if not isinstance(docs, list):
            return []

    results = [_doc_to_details(doc) for doc in docs]
    return [details for details in results if details is not None]


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
