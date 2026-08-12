"""Open Library wrapper tests.

Every response here comes from a mock transport, so no test touches the real
catalogue.  The payloads are trimmed copies of real Open Library responses,
including the awkward parts: an edition ISBN list in no useful order, a missing
author, and a free-text publication date.
"""

import httpx
import pytest

from app import lookup as lookup_module
from app import openlibrary


SEARCH_DOC = {
    "numFound": 224,
    "docs": [
        {
            "title": "The Hobbit",
            "author_name": ["J.R.R. Tolkien"],
            "first_publish_year": 1937,
            "isbn": ["0618002219", "9780261103344"],
            "cover_i": 14627509,
        },
        {
            "title": "The Hobbit: Graphic Novel",
            "author_name": ["Chuck Dixon"],
            "first_publish_year": 1989,
            "isbn": ["9780345368584"],
        },
    ],
}


def json_route(payload, status_code: int = 200):
    """A handler answering any request with one JSON payload."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json=payload)

    return handler


def test_search_retries_broad_query_when_title_index_call_fails(
    mock_openlibrary,
) -> None:
    """A slow or failed title-index request still gets the broad-query answer."""

    def handler(request: httpx.Request) -> httpx.Response:
        if "title=" in str(request.url):
            raise httpx.ConnectError("title index timeout")
        return httpx.Response(200, json=SEARCH_DOC)

    mock_openlibrary(handler)

    results = openlibrary.search_book("The Hobbit").results

    assert len(results) == 2
    assert results[0].title == "The Hobbit"


def test_get_book_details_falls_back_to_isbn_search_when_books_api_fails(
    mock_openlibrary,
) -> None:
    """A failed books-API call still resolves the ISBN via the search index."""

    def handler(request: httpx.Request) -> httpx.Response:
        if "/api/books" in str(request.url):
            raise httpx.ConnectError("books API timeout")
        return httpx.Response(
            200,
            json={
                "numFound": 1,
                "docs": [
                    {
                        "title": "The Hobbit",
                        "author_name": ["J.R.R. Tolkien"],
                        "first_publish_year": 1937,
                        "isbn": ["9780261103344"],
                        "cover_i": 14627509,
                    }
                ],
            },
        )

    mock_openlibrary(handler)

    details = openlibrary.get_book_details("9780261103344")

    assert details is not None
    assert details.title == "The Hobbit"
    assert details.isbn == "9780261103344"


def test_search_by_subject_queries_the_subject_index(mock_openlibrary) -> None:
    """A recommendation query hits the subject index and maps the docs it gets."""
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, json=SEARCH_DOC)

    mock_openlibrary(handler)

    page = openlibrary.search_by_subject("science fiction")

    assert "subject=science+fiction" in seen["url"]
    assert page.total == 224
    assert [book.title for book in page.results] == [
        "The Hobbit",
        "The Hobbit: Graphic Novel",
    ]


def test_search_book_maps_a_real_search_response(mock_openlibrary) -> None:
    mock_openlibrary(json_route(SEARCH_DOC))

    results = openlibrary.search_book("The Hobbit").results

    assert len(results) == 2
    first = results[0]
    assert first.title == "The Hobbit"
    assert first.author == "J.R.R. Tolkien"
    assert first.year == 1937
    assert first.isbn == "9780261103344"  # the 13-digit one, not the first listed
    assert first.cover_url == "https://covers.openlibrary.org/b/id/14627509-M.jpg"


def test_search_falls_back_to_an_isbn_cover_when_there_is_no_cover_id(
    mock_openlibrary,
) -> None:
    mock_openlibrary(json_route(SEARCH_DOC))

    results = openlibrary.search_book("The Hobbit").results

    assert results[1].cover_url == "https://covers.openlibrary.org/b/isbn/9780345368584-M.jpg"


def test_search_sends_the_title_and_asks_for_named_fields(mock_openlibrary) -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(request.url.params)
        seen["path"] = request.url.path
        return httpx.Response(200, json={"docs": []})

    mock_openlibrary(handler)
    openlibrary.search_book("  The Hobbit  ")

    assert seen["path"] == "/search.json"
    assert seen["title"] == "The Hobbit"
    assert seen["fields"] == openlibrary.SEARCH_FIELDS


def test_search_uses_a_broad_query_when_the_title_field_has_no_match(
    mock_openlibrary,
) -> None:
    requests: list[dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        params = dict(request.url.params)
        requests.append(params)
        if "title" in params:
            return httpx.Response(200, json={"docs": []})
        return httpx.Response(
            200,
            json={
                "docs": [
                    {
                        "title": "Harry Potter and the Philosopher's Stone",
                        "author_name": ["J. K. Rowling"],
                        "isbn": ["9780747532699"],
                    }
                ]
            },
        )

    mock_openlibrary(handler)

    results = openlibrary.search_book("神秘的魔法石").results

    assert len(requests) == 2
    assert requests[0]["title"] == "神秘的魔法石"
    assert requests[1]["q"] == "神秘的魔法石"
    assert results[0].isbn == "9780747532699"


def test_search_returns_nothing_for_a_blank_title_without_a_request(
    mock_openlibrary,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("a blank title must not hit the network")

    mock_openlibrary(handler)

    assert openlibrary.search_book("   ").results == []


def test_search_drops_a_doc_with_no_title(mock_openlibrary) -> None:
    mock_openlibrary(json_route({"docs": [{"author_name": ["Nobody"]}, {"title": "Dune"}]}))

    results = openlibrary.search_book("dune").results

    assert [details.title for details in results] == ["Dune"]


def test_search_tolerates_a_doc_with_no_author_year_or_isbn(mock_openlibrary) -> None:
    mock_openlibrary(json_route({"docs": [{"title": "An Untouched Record"}]}))

    details = openlibrary.search_book("an untouched record").results[0]

    assert details.author is None
    assert details.year is None
    assert details.isbn is None
    assert details.cover_url is None


def test_search_raises_lookup_unavailable_on_a_server_error(mock_openlibrary) -> None:
    mock_openlibrary(json_route({"error": "boom"}, status_code=503))

    with pytest.raises(openlibrary.LookupUnavailable):
        openlibrary.search_book("The Hobbit")


def test_search_raises_lookup_unavailable_on_a_timeout(mock_openlibrary) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("too slow", request=request)

    mock_openlibrary(handler)

    with pytest.raises(openlibrary.LookupUnavailable):
        openlibrary.search_book("The Hobbit")


def test_search_raises_lookup_unavailable_on_unparseable_json(mock_openlibrary) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>not json</html>")

    mock_openlibrary(handler)

    with pytest.raises(openlibrary.LookupUnavailable):
        openlibrary.search_book("The Hobbit")


ISBN_RECORD = {
    "ISBN:9780261103344": {
        "title": "The Hobbit",
        "authors": [{"name": "J.R.R. Tolkien"}],
        "publish_date": "March 2011",
        "cover": {"medium": "https://covers.openlibrary.org/b/id/10236414-M.jpg"},
    }
}


def test_get_book_details_maps_an_isbn_record(mock_openlibrary) -> None:
    mock_openlibrary(json_route(ISBN_RECORD))

    details = openlibrary.get_book_details("9780261103344")

    assert details is not None
    assert details.title == "The Hobbit"
    assert details.author == "J.R.R. Tolkien"
    assert details.year == 2011  # pulled out of the free-text publish_date
    assert details.cover_url == "https://covers.openlibrary.org/b/id/10236414-M.jpg"


def test_get_book_details_normalises_a_hyphenated_isbn(mock_openlibrary) -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(request.url.params)
        return httpx.Response(200, json=ISBN_RECORD)

    mock_openlibrary(handler)
    details = openlibrary.get_book_details("978-0-261-10334-4")

    assert seen["bibkeys"] == "ISBN:9780261103344"
    assert details is not None
    assert details.isbn == "9780261103344"


def test_get_book_details_returns_none_for_an_unknown_isbn(mock_openlibrary) -> None:
    mock_openlibrary(json_route({}))

    assert openlibrary.get_book_details("9999999999999") is None


def test_get_book_details_returns_none_for_a_blank_isbn(mock_openlibrary) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("a blank ISBN must not hit the network")

    mock_openlibrary(handler)

    assert openlibrary.get_book_details("  ") is None


def test_lookup_prefers_open_library_over_the_seed(mock_openlibrary) -> None:
    """A live answer wins even for a title the seed also knows."""
    mock_openlibrary(
        json_route(
            {
                "docs": [
                    {
                        "title": "The Hobbit",
                        "author_name": ["Live Catalogue Author"],
                        "first_publish_year": 1937,
                        "isbn": ["9780261103344"],
                    }
                ]
            }
        )
    )

    details = lookup_module.lookup("The Hobbit")

    assert details is not None
    assert details.author == "Live Catalogue Author"


def test_lookup_falls_back_to_the_seed_when_open_library_is_down(
    mock_openlibrary,
) -> None:
    mock_openlibrary(json_route({"error": "boom"}, status_code=500))

    details = lookup_module.lookup("The Hobbit")

    assert details is not None
    assert details.author == "J. R. R. Tolkien"  # the seeded spelling


def test_lookup_falls_back_to_the_seed_when_open_library_has_no_match(
    mock_openlibrary,
) -> None:
    mock_openlibrary(json_route({"docs": []}))

    details = lookup_module.lookup("The Hobbit")

    assert details is not None
    assert details.author == "J. R. R. Tolkien"


def test_lookup_returns_none_when_neither_backend_knows_the_title(
    mock_openlibrary,
) -> None:
    mock_openlibrary(json_route({"docs": []}))

    assert lookup_module.lookup("A Title Nobody Has Ever Catalogued") is None


def test_add_a_book_uses_open_library(client, mock_openlibrary) -> None:
    """The POST /books path end to end against a mocked catalogue."""
    mock_openlibrary(
        json_route(
            {
                "docs": [
                    {
                        "title": "Piranesi",
                        "author_name": ["Susanna Clarke"],
                        "first_publish_year": 2020,
                        "isbn": ["9781635575637"],
                        "cover_i": 10514417,
                    }
                ]
            }
        )
    )

    response = client.post("/books", json={"title": "Piranesi", "shelf": "wishlist"})

    assert response.status_code == 201
    body = response.json()
    assert body["author"] == "Susanna Clarke"
    assert body["year"] == 2020
    assert body["isbn"] == "9781635575637"
    assert body["details_pending"] is False


def test_add_a_book_is_rejected_when_the_catalogue_cannot_supply_an_isbn(
    client, mock_openlibrary
) -> None:
    """An outage on an unseeded title must not create an ISBN-less book."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route to host", request=request)

    mock_openlibrary(handler)

    response = client.post("/books", json={"title": "A Book Nobody Seeded"})

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "isbn_not_found"
    assert client.get("/books").json() == []


def test_unknown_backend_name_falls_back_to_the_default(monkeypatch) -> None:
    monkeypatch.setenv("SHELF_LIFE_LOOKUP_BACKEND", "goodreads")

    assert lookup_module.active_backend() == lookup_module.DEFAULT_BACKEND


def test_timeout_ignores_a_nonsense_environment_value(monkeypatch) -> None:
    monkeypatch.setenv(openlibrary.TIMEOUT_ENV, "soon")
    assert openlibrary.timeout() == openlibrary.DEFAULT_TIMEOUT

    monkeypatch.setenv(openlibrary.TIMEOUT_ENV, "-1")
    assert openlibrary.timeout() == openlibrary.DEFAULT_TIMEOUT

    monkeypatch.setenv(openlibrary.TIMEOUT_ENV, "2.5")
    assert openlibrary.timeout() == 2.5
def test_subjects_for_isbn_parses_and_cleans(mock_openlibrary) -> None:
    """Open Library subject lists become cleaned, deduplicated suggestions."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "numFound": 1,
                "docs": [
                    {
                        "subject": [
                            "Science fiction",
                            "Science fiction",
                            "  Aliens  ",
                            "fiction",
                            "novel",
                            "Chinese fiction",
                        ]
                    }
                ],
            },
        )

    mock_openlibrary(handler)

    assert openlibrary.subjects_for_isbn("9781800249158") == [
        "Science fiction",
        "Aliens",
        "Chinese fiction",
    ]


def test_subjects_for_isbn_returns_empty_for_no_docs(mock_openlibrary) -> None:
    mock_openlibrary(json_route({"numFound": 0, "docs": []}))

    assert openlibrary.subjects_for_isbn("9780000000000") == []


def test_subjects_for_isbn_hides_unavailable_from_callers(mock_openlibrary) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("subjects API timeout")

    mock_openlibrary(handler)

    assert openlibrary.subjects_for_isbn("9781800249158") == []

def test_suggest_categories_maps_subjects_to_few_broad_buckets() -> None:
    raw = [
        "Science fiction",
        "Fantasy",
        "Human-alien encounters",
        "Chinese Science fiction",
        "Murder mystery",
        "History of China",
    ]

    assert openlibrary.suggest_categories(raw) == [
        "Sci-Fi & Fantasy",
        "Mystery & Thriller",
        "Non-fiction",
    ]