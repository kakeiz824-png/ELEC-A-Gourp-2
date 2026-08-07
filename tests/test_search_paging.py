"""Paging tests, and the ISBN confirmation that paging made necessary.

Capping the result list at five was hiding books: a search for Harry Potter could
not show seven novels. Paging fixes that, and in doing so it breaks confirming an
addition by re-running the search -- the chosen book may have come from page
seven, and catalogue relevance order shifts between requests. So an addition is
confirmed by asking the catalogue about the ISBN instead, which is what these
tests pin down.

Every response comes from a mock transport or the seed.
"""

import asyncio

import httpx
import pytest
from fastmcp import Client

import app.services.search as search_service
from app import lookup as lookup_module
from app import mcp_client, openlibrary
from app.details import BookDetails, SearchPage
from app.openlibrary import LookupUnavailable
from mcp_server import server


SEEDED_ISBN = "9780451524935"  # Nineteen Eighty-Four, in seed/books.json


def json_route(payload, status_code: int = 200):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json=payload)

    return handler


def numbered(count: int, *, start: int = 0) -> list[BookDetails]:
    """Distinct ISBN-bearing results, so paging can be told apart by content."""
    return [
        BookDetails(
            title=f"Book {start + index}",
            author="An Author",
            isbn=f"97800000{start + index:05d}",
        )
        for index in range(count)
    ]


def recorder(total: int):
    """A stand-in search that reports what paging it was asked for."""
    calls: list[tuple[int, int]] = []

    def search(query: str, *, limit: int = 5, offset: int = 0) -> SearchPage:
        calls.append((limit, offset))
        remaining = max(0, min(limit, total - offset))
        return SearchPage(results=numbered(remaining, start=offset), total=total)

    return search, calls


# --------------------------------------------------------------------------
# Paging at the Open Library boundary
# --------------------------------------------------------------------------


def test_a_title_search_passes_paging_to_the_catalogue(mock_openlibrary) -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(request.url.params)
        return httpx.Response(200, json={"numFound": 90, "docs": []})

    mock_openlibrary(handler)
    openlibrary.search_book("Harry Potter", limit=10, offset=30)

    assert seen["title"] == "Harry Potter"
    assert seen["limit"] == "10"
    assert seen["offset"] == "30"


def test_the_broad_query_fallback_is_decided_by_the_total_not_the_page(
    mock_openlibrary,
) -> None:
    """Page 9 of a real result set is empty; that is not a reason to re-search."""
    requests: list[dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(dict(request.url.params))
        return httpx.Response(200, json={"numFound": 40, "docs": []})

    mock_openlibrary(handler)
    page = openlibrary.search_book("Harry Potter", limit=5, offset=200)

    assert len(requests) == 1
    assert "q" not in requests[0]
    assert page.results == []
    assert page.total == 40


def test_a_title_with_no_match_at_all_still_falls_back_to_the_broad_query(
    mock_openlibrary,
) -> None:
    requests: list[dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        params = dict(request.url.params)
        requests.append(params)
        if "title" in params:
            return httpx.Response(200, json={"numFound": 0, "docs": []})
        return httpx.Response(
            200,
            json={
                "numFound": 1,
                "docs": [{"title": "Found Broadly", "isbn": ["9780000000001"]}],
            },
        )

    mock_openlibrary(handler)
    page = openlibrary.search_book("Something Obscure")

    assert len(requests) == 2
    assert [book.title for book in page.results] == ["Found Broadly"]


# --------------------------------------------------------------------------
# Paging in the lookup boundary
# --------------------------------------------------------------------------


def test_the_seed_pages_the_same_way_the_catalogue_does() -> None:
    first = lookup_module.search_seed_author("Tolkien", limit=1, offset=0)
    second = lookup_module.search_seed_author("Tolkien", limit=1, offset=1)

    assert [book.title for book in first.results] == ["The Hobbit"]
    assert [book.title for book in second.results] == ["The Lord of the Rings"]
    assert first.total == second.total == 2


def test_a_page_past_the_end_does_not_fall_back_to_the_seed(
    mock_openlibrary,
) -> None:
    """Otherwise The Hobbit turns up on page 40 of a search for anything."""
    mock_openlibrary(json_route({"numFound": 257, "docs": []}))

    page = lookup_module.search_author("Ursula K. Le Guin", limit=10, offset=2000)

    assert page.results == []
    assert page.total == 257


# --------------------------------------------------------------------------
# Paging in the search service
# --------------------------------------------------------------------------


def test_the_page_number_becomes_an_offset(monkeypatch) -> None:
    search, calls = recorder(total=95)
    monkeypatch.setattr(search_service, "search_book", search)

    search_service.by_title("Harry Potter", page=1, per_page=10)
    search_service.by_title("Harry Potter", page=4, per_page=10)

    assert calls == [(10, 0), (10, 30)]


def test_the_page_count_comes_from_the_catalogue_total(monkeypatch) -> None:
    search, _ = recorder(total=95)
    monkeypatch.setattr(search_service, "search_author", search)

    page = search_service.by_author("J. K. Rowling", page=2, per_page=10)

    assert page.total == 95
    assert page.pages == 10  # 95 results do not fit in nine pages
    assert page.page == 2
    assert page.per_page == 10


def test_an_empty_result_set_still_reports_one_page(monkeypatch) -> None:
    search, _ = recorder(total=0)
    monkeypatch.setattr(search_service, "search_book", search)

    page = search_service.by_title("Nothing At All")

    assert page.candidates == []
    assert page.pages == 1


def test_a_page_can_be_short_while_later_pages_still_exist(monkeypatch) -> None:
    """Candidates lacking an ISBN are dropped after the page is fetched."""

    def search(query: str, *, limit: int = 5, offset: int = 0) -> SearchPage:
        return SearchPage(
            results=[BookDetails(title="No ISBN"), *numbered(2)], total=90
        )

    monkeypatch.setattr(search_service, "search_book", search)
    page = search_service.by_title("Harry Potter", page=1, per_page=10)

    assert len(page.candidates) == 2
    assert page.pages == 9


def test_one_page_never_offers_the_same_isbn_twice(monkeypatch) -> None:
    def search(query: str, *, limit: int = 5, offset: int = 0) -> SearchPage:
        return SearchPage(
            results=[
                BookDetails(title="Edition A", isbn="978-0-451-52493-5"),
                BookDetails(title="Edition B", isbn="9780451524935"),
            ],
            total=2,
        )

    monkeypatch.setattr(search_service, "search_book", search)
    page = search_service.by_title("Nineteen Eighty-Four")

    assert [book.title for book in page.candidates] == ["Edition A"]
    assert page.candidates[0].isbn == "9780451524935"  # normalised, not as sent


# --------------------------------------------------------------------------
# The paged endpoint
# --------------------------------------------------------------------------


def test_the_endpoint_reports_where_the_page_sits(client) -> None:
    response = client.get(
        "/books/search", params={"author": "Tolkien", "per_page": 1, "page": 2}
    )

    assert response.status_code == 200
    body = response.json()
    assert [book["title"] for book in body["items"]] == ["The Lord of the Rings"]
    assert body["page"] == 2
    assert body["pages"] == 2
    assert body["per_page"] == 1
    assert body["total"] == 2


def test_the_endpoint_serves_an_empty_page_past_the_end(client) -> None:
    response = client.get(
        "/books/search", params={"author": "Tolkien", "per_page": 1, "page": 9}
    )

    assert response.status_code == 200
    assert response.json()["items"] == []
    assert response.json()["pages"] == 2


def test_the_endpoint_rejects_paging_it_cannot_serve(client) -> None:
    for params in (
        {"title": "The Hobbit", "page": 0},
        {"title": "The Hobbit", "per_page": 0},
        {"title": "The Hobbit", "per_page": search_service.MAX_PER_PAGE + 1},
    ):
        assert client.get("/books/search", params=params).status_code == 422


# --------------------------------------------------------------------------
# Confirming an addition by ISBN
# --------------------------------------------------------------------------


def test_an_addition_is_confirmed_without_repeating_the_search(client) -> None:
    """A candidate from page seven must be addable; no search runs here at all."""
    response = client.post(
        "/books", json={"title": "Nineteen Eighty-Four", "isbn": SEEDED_ISBN}
    )

    assert response.status_code == 201
    assert response.json()["isbn"] == SEEDED_ISBN


def test_submitted_metadata_is_replaced_by_the_catalogues(client) -> None:
    """The ISBN identifies the book, so nothing the client claims is trusted."""
    response = client.post(
        "/books",
        json={"title": "A Title The Client Made Up", "isbn": SEEDED_ISBN},
    )

    assert response.status_code == 201
    book = response.json()
    assert book["title"] == "Nineteen Eighty-Four"
    assert book["author"] == "George Orwell"
    assert book["year"] == 1949


def test_an_isbn_the_catalogue_does_not_know_is_rejected(client) -> None:
    response = client.post(
        "/books", json={"title": "Invented Book", "isbn": "9999999999999"}
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "isbn_not_found"
    assert client.get("/books").json() == []


def test_an_isbn_lookup_outage_does_not_create_a_book(client, monkeypatch) -> None:
    def explode(isbn: str):
        raise RuntimeError("the catalogue is unreachable")

    monkeypatch.setattr("app.routers.books.details_for_isbn", explode)

    response = client.post("/books", json={"title": "Anything", "isbn": SEEDED_ISBN})

    assert response.status_code == 404
    assert client.get("/books").json() == []


# --------------------------------------------------------------------------
# The ISBN lookup tool behind it
# --------------------------------------------------------------------------


def call_details_tool(isbn: str):
    async def call():
        async with Client(server.mcp) as client:
            return await client.call_tool(
                "get_book_details", {"isbn": isbn}, raise_on_error=False
            )

    return asyncio.run(call())


def test_the_details_tool_returns_one_readable_book(monkeypatch) -> None:
    monkeypatch.setattr(
        server,
        "open_library_details",
        lambda isbn: BookDetails(
            title="Nineteen Eighty-Four",
            author="George Orwell",
            isbn=isbn,
            year=1949,
        ),
    )

    result = call_details_tool(SEEDED_ISBN)

    assert result.content[0].text.startswith(f"Found ISBN {SEEDED_ISBN}:")
    assert result.structured_content["status"] == "ok"
    assert result.structured_content["book"]["author"] == "George Orwell"


def test_the_details_tool_rejects_a_blank_isbn_without_a_lookup(monkeypatch) -> None:
    def fail_if_called(isbn: str):
        raise AssertionError("blank input must not call Open Library")

    monkeypatch.setattr(server, "open_library_details", fail_if_called)

    assert call_details_tool("  ").content[0].text == "Error: isbn must not be blank."


def test_the_details_tool_reports_an_unknown_isbn(monkeypatch) -> None:
    monkeypatch.setattr(server, "open_library_details", lambda isbn: None)

    result = call_details_tool("9999999999999")

    assert result.structured_content["status"] == "no_match"
    assert result.structured_content["book"] is None


def test_the_details_tool_hides_catalogue_failures(monkeypatch) -> None:
    def unavailable(isbn: str):
        raise LookupUnavailable("internal network details")

    monkeypatch.setattr(server, "open_library_details", unavailable)

    text = call_details_tool(SEEDED_ISBN).content[0].text

    assert "internal network details" not in text
    assert "temporarily unavailable" in text


def test_the_client_converts_the_details_tool_result(monkeypatch) -> None:
    expected = BookDetails(
        title="Nineteen Eighty-Four", author="George Orwell", isbn=SEEDED_ISBN
    )
    monkeypatch.setattr(server, "open_library_details", lambda isbn: expected)

    assert mcp_client.get_book_details(SEEDED_ISBN) == expected


def test_the_client_returns_none_for_an_unknown_isbn(monkeypatch) -> None:
    monkeypatch.setattr(server, "open_library_details", lambda isbn: None)

    assert mcp_client.get_book_details("9999999999999") is None


def test_the_client_maps_a_details_failure_to_mcp_unavailable(monkeypatch) -> None:
    def unavailable(isbn: str):
        raise LookupUnavailable("internal network details")

    monkeypatch.setattr(server, "open_library_details", unavailable)

    with pytest.raises(mcp_client.MCPUnavailable):
        mcp_client.get_book_details(SEEDED_ISBN)


def test_the_isbn_lookup_falls_back_to_the_seed_when_mcp_is_unavailable(
    monkeypatch,
) -> None:
    def unavailable(isbn: str):
        raise mcp_client.MCPUnavailable("server is down")

    monkeypatch.setenv(lookup_module.BACKEND_ENV, lookup_module.MCP_BACKEND)
    monkeypatch.setattr(mcp_client, "get_book_details", unavailable)

    details = lookup_module.details_for_isbn(SEEDED_ISBN)

    assert details is not None
    assert details.title == "Nineteen Eighty-Four"

def test_the_details_tool_hides_unexpected_exceptions(monkeypatch) -> None:
    """An unexpected bug must look like an outage, and stay out of client text."""

    def explode(isbn: str):
        raise RuntimeError("internal mapping bug")

    monkeypatch.setattr(server, "open_library_details", explode)

    result = call_details_tool(SEEDED_ISBN)

    assert result.structured_content == {
        "status": "unavailable",
        "books": [],
        "total": 0,
    }
    text = result.content[0].text
    assert "internal mapping bug" not in text
    assert "temporarily unavailable" in text


def test_the_title_search_falls_back_to_the_seed_when_mcp_is_unavailable(
    monkeypatch,
) -> None:
    """An unexpected tool error must degrade to the seed like an outage."""

    def explode(title: str, **paging):
        raise RuntimeError("internal mapping bug")

    monkeypatch.setenv(lookup_module.BACKEND_ENV, lookup_module.MCP_BACKEND)
    monkeypatch.setattr(server, "search_open_library", explode)

    page = lookup_module.search_book("The Hobbit")

    assert page.results
    assert page.results[0].title == "The Hobbit"
    assert page.results[0].author == "J. R. R. Tolkien"
