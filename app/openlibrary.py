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
AUTHOR_URL = "https://openlibrary.org/authors/{key}.json"

# Asking for named fields keeps the response small: an unfiltered search doc
# carries hundreds of keys, including every edition ISBN.
SEARCH_FIELDS = "title,author_name,first_publish_year,isbn,cover_i"
# The author profile resolves a name to an OLID through the fast book-search
# index (``author=`` on ``/search.json``) -- the same reliable endpoint the book
# list already uses -- rather than the slow ``/search/authors.json`` author
# index, which routinely takes several seconds and times out.
AUTHOR_SEARCH_FIELDS = "author_key,author_name"
SEARCH_LIMIT = 5

# Open Library is often slow from a free hosting tier: healthy responses can
# take several seconds, so a tight 5s budget made real queries time out and
# fall back to the tiny offline seed. 10s keeps the app responsive while giving
# live results room to arrive. Override per environment with
# ``SHELF_LIFE_OPENLIBRARY_TIMEOUT`` when the network is faster or slower.
DEFAULT_TIMEOUT = 10.0
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

    try:
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
    except LookupUnavailable:
        # A slow or failed title-index request must not blank the whole
        # search: the broad query hits a different index path and may still
        # answer, so fall through to it instead of giving up.
        docs, total = [], 0

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


def _isbn_search_details(key: str) -> BookDetails | None:
    """Resolve one ISBN through the search index instead of the books API."""
    payload = _get_json(
        SEARCH_URL,
        {"q": f"isbn:{key}", "limit": 1, "fields": SEARCH_FIELDS},
    )
    docs, _ = _docs(payload, "isbn search")
    for doc in docs:
        if not isinstance(doc, dict):
            continue
        isbns = doc.get("isbn")
        if not isinstance(isbns, list):
            continue
        if any(
            str(value).strip().replace("-", "").replace(" ", "") == key
            for value in isbns
        ):
            details = _doc_to_details(doc)
            if details is not None:
                return details
    return None


def get_book_details(isbn: str) -> BookDetails | None:
    """Fetch the record for one ISBN, or ``None`` if the catalogue has none."""
    key = isbn.strip().replace("-", "").replace(" ", "")
    if not key:
        return None

    try:
        payload = _get_json(
            BOOKS_URL, {"bibkeys": f"ISBN:{key}", "format": "json", "jscmd": "data"}
        )
    except LookupUnavailable:
        # The books API can be slow or transiently unavailable; the search
        # index resolves the same ISBN through a different code path, so fall
        # back to it before letting the add fail.
        return _isbn_search_details(key)
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


_GENERIC_SUBJECTS = {"fiction", "novel", "specimens", "tales", "stories"}
MAX_SUBJECT_LENGTH = 50
MAX_SUBJECTS = 10


def subjects_for_isbn(isbn: str) -> list[str]:
    """Top cleaned subject suggestions for one ISBN, best-effort.

    The books API does not return subjects, so this uses the search index (the
    same endpoint family as the ISBN-search fallback) and never raises: a
    missing or slow catalogue simply yields no suggestions.
    """
    key = isbn.strip().replace("-", "").replace(" ", "")
    if not key:
        return []
    try:
        payload = _get_json(
            SEARCH_URL, {"q": f"isbn:{key}", "limit": 1, "fields": "subject"}
        )
        docs, _ = _docs(payload, "subject search")
    except LookupUnavailable:
        return []
    if not docs or not isinstance(docs[0], dict):
        return []

    raw = docs[0].get("subject")
    if not isinstance(raw, list):
        return []

    seen: set[str] = set()
    subjects: list[str] = []
    for value in raw:
        if not isinstance(value, str):
            continue
        name = value.strip()
        folded = name.casefold()
        if not name or folded in seen or folded in _GENERIC_SUBJECTS:
            continue
        if len(name) > MAX_SUBJECT_LENGTH:
            continue
        seen.add(folded)
        subjects.append(name)
        if len(subjects) >= MAX_SUBJECTS:
            break
    return subjects


def _text(value: object) -> str | None:
    """A stripped non-empty string, or ``None`` for anything else."""
    return value.strip() if isinstance(value, str) and value.strip() else None


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


def _first_author_photo(photos: object) -> str | None:
    """The URL of the first usable author photo id, or ``None``."""
    if not isinstance(photos, list):
        return None
    for photo_id in photos:
        url = author_photo_url_by_id(photo_id)
        if url:
            return url
    return None


def _author_identity(doc: object, tokens: list[str]) -> tuple[str, str | None] | None:
    """The queried author's ``(OLID, display name)`` from a book-search doc.

    A ``/search.json`` book doc lists ``author_key`` and ``author_name`` in
    lockstep. The top hit for an ``author=`` query is normally by that author, so
    the first pair is the right one -- except on an anthology whose primary
    author is somebody else, where the queried name sits further down the list.
    The aligned name carrying every query token is preferred so "Ted Chiang"
    resolves to Chiang and not the editor credited first.
    """
    if not isinstance(doc, dict):
        return None
    keys = doc.get("author_key")
    if not isinstance(keys, list) or not keys:
        return None
    names = doc.get("author_name")
    names = names if isinstance(names, list) else []

    chosen = 0
    for index, candidate in enumerate(names):
        if isinstance(candidate, str) and all(
            token in normalise(candidate) for token in tokens
        ):
            chosen = index
            break

    key = keys[chosen] if chosen < len(keys) else keys[0]
    if not isinstance(key, str) or not key.strip():
        return None
    name = names[chosen] if chosen < len(names) else None
    display = name.strip() if isinstance(name, str) and name.strip() else None
    return key.strip().rsplit("/", 1)[-1], display


def get_author_details(name: str) -> AuthorDetails | None:
    """Fetch an author's profile by name, or ``None`` if none matches.

    Resolution goes through the fast book-search index rather than the slow
    ``/search/authors.json`` author index: an ``author=`` query returns the
    author's OLID in ``author_key``, from the same endpoint the book list
    already relies on.  The author record then supplies the biography, dates, and
    photo, but that second call is best-effort -- if it is slow or fails, the
    profile still comes back with the name and a hidden bio rather than vanishing
    entirely.  A name that matches nobody yields ``None``, and a failure to even
    resolve the name surfaces as ``LookupUnavailable`` for the caller to treat as
    "no profile".
    """
    query = normalise(name)
    if not query:
        return None

    docs, _ = _docs(
        _get_json(
            SEARCH_URL,
            {"author": name.strip(), "limit": 1, "fields": AUTHOR_SEARCH_FIELDS},
        ),
        "author profile search",
    )
    identity = _author_identity(docs[0], _author_tokens(name)) if docs else None
    if identity is None:
        return None
    key, display_name = identity

    try:
        record = _get_json(AUTHOR_URL.format(key=key), {})
    except LookupUnavailable:
        # Best-effort: the name is already resolved, so a slow or failing record
        # fetch drops only the biography, not the whole panel.
        record = None
    if not isinstance(record, dict):
        record = {}

    return AuthorDetails(
        name=_text(record.get("name")) or display_name or name.strip(),
        bio=_author_bio(record.get("bio")),
        birth_date=_text(record.get("birth_date")),
        death_date=_text(record.get("death_date")),
        work_count=None,
        photo_url=_first_author_photo(record.get("photos")),
    )
