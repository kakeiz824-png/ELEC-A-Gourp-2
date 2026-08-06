"""Author search tests, from the Open Library call up to the HTTP endpoint.

Searching an author's name as a title is what the feature exists to fix: Open
Library's ``title=`` index matches biographies and study guides whose titles
contain the name, so it answers "George Orwell" with books *about* Orwell.  The
payloads below are trimmed copies of real responses, including the awkward part
that made the relevance filter necessary: an ``author=`` search also returns
anthologies the author only contributed one story to.

Every response comes from a mock transport or the seed, so no test here touches
the real catalogue.
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


LE_GUIN = {
    "numFound": 257,
    "docs": [
        {
            "title": "A Wizard of Earthsea",
            "author_name": ["Ursula K. Le Guin"],
            "first_publish_year": 1968,
            "isbn": ["0553262505", "9780553262506"],
            "cover_i": 8231990,
        },
        {
            "title": "The Left Hand of Darkness",
            "author_name": ["Ursula K. Le Guin"],
            "first_publish_year": 1969,
            "isbn": ["9780441478125"],
        },
        {
            # An anthology she wrote one story for. Its primary author is the
            # editor, so it is not one of "her books".
            "title": "The Fantasy Hall of Fame",
            "author_name": ["Robert Silverberg", "Ursula K. Le Guin"],
            "first_publish_year": 1998,
            "isbn": ["9780061052156"],
        },
    ],
}


def json_route(payload, status_code: int = 200):
    """A handler answering any request with one JSON payload."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json=payload)

    return handler


def details(title: str, author: str, isbn: str) -> BookDetails:
    """A minimal catalogue result for the service and endpoint tests."""
    return BookDetails(title=title, author=author, isbn=isbn)


def one_page(*results: BookDetails, total: int | None = None):
    """A stand-in search that ignores paging and answers with these results."""

    def search(query: str, *, limit: int = 5, offset: int = 0) -> SearchPage:
        return SearchPage(
            results=list(results), total=len(results) if total is None else total
        )

    return search


# --------------------------------------------------------------------------
# The Open Library author index
# --------------------------------------------------------------------------


def test_author_search_asks_the_author_index_for_named_fields(
    mock_openlibrary,
) -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(request.url.params)
        seen["path"] = request.url.path
        return httpx.Response(200, json={"docs": []})

    mock_openlibrary(handler)
    openlibrary.search_author("  Ursula K. Le Guin  ", limit=10, offset=20)

    assert seen["path"] == "/search.json"
    assert seen["author"] == "Ursula K. Le Guin"
    assert "title" not in seen
    assert seen["limit"] == "10"
    assert seen["offset"] == "20"
    assert seen["fields"] == openlibrary.SEARCH_FIELDS


def test_author_search_maps_the_authors_own_books(mock_openlibrary) -> None:
    mock_openlibrary(json_route(LE_GUIN))

    page = openlibrary.search_author("Ursula K. Le Guin")

    assert [book.title for book in page.results] == [
        "A Wizard of Earthsea",
        "The Left Hand of Darkness",
    ]
    first = page.results[0]
    assert first.author == "Ursula K. Le Guin"
    assert first.year == 1968
    assert first.isbn == "9780553262506"  # the 13-digit one, not the first listed
    assert first.cover_url == "https://covers.openlibrary.org/b/id/8231990-M.jpg"


def test_author_search_reports_the_catalogue_total_not_the_page_length(
    mock_openlibrary,
) -> None:
    """"Page 3 of 26" has to be answerable without fetching the other 25."""
    mock_openlibrary(json_route(LE_GUIN))

    page = openlibrary.search_author("Ursula K. Le Guin")

    assert page.total == 257
    assert len(page.results) == 2


def test_author_search_drops_an_anthology_credited_to_someone_else(
    mock_openlibrary,
) -> None:
    mock_openlibrary(json_route(LE_GUIN))

    titles = [
        book.title for book in openlibrary.search_author("Ursula K. Le Guin").results
    ]

    assert "The Fantasy Hall of Fame" not in titles


def test_author_search_matches_a_name_written_with_spaced_initials(
    mock_openlibrary,
) -> None:
    """The query "J. R. R. Tolkien" has to reach the catalogue's "J.R.R. Tolkien"."""
    mock_openlibrary(
        json_route(
            {
                "docs": [
                    {
                        "title": "The Hobbit",
                        "author_name": ["J.R.R. Tolkien"],
                        "isbn": ["9780261103344"],
                    },
                    {
                        "title": "Tolkien: A Biography",
                        "author_name": ["Humphrey Carpenter"],
                        "isbn": ["9780618057023"],
                    },
                ]
            }
        )
    )

    page = openlibrary.search_author("J. R. R. Tolkien")

    assert [book.title for book in page.results] == ["The Hobbit"]


def test_author_search_keeps_everything_rather_than_filtering_to_nothing(
    mock_openlibrary,
) -> None:
    """An author credited only as a co-author must rank low, not vanish."""
    mock_openlibrary(
        json_route(
            {
                "docs": [
                    {
                        "title": "Vanishing Acts",
                        "author_name": ["Ellen Datlow", "Ted Chiang"],
                        "isbn": ["9780765300355"],
                    }
                ]
            }
        )
    )

    page = openlibrary.search_author("Ted Chiang")

    assert [book.title for book in page.results] == ["Vanishing Acts"]


def test_author_search_returns_nothing_for_a_blank_name_without_a_request(
    mock_openlibrary,
) -> None:
    def fail_if_called(request: httpx.Request) -> httpx.Response:
        raise AssertionError("a blank author must not reach Open Library")

    mock_openlibrary(fail_if_called)

    page = openlibrary.search_author("   ")

    assert page.results == []
    assert page.total == 0


def test_author_search_returns_nothing_when_the_catalogue_has_no_docs(
    mock_openlibrary,
) -> None:
    mock_openlibrary(json_route({"numFound": 0, "docs": []}))

    assert openlibrary.search_author("Nobody At All").results == []


def test_author_search_raises_lookup_unavailable_on_a_server_error(
    mock_openlibrary,
) -> None:
    mock_openlibrary(json_route({"docs": []}, status_code=500))

    with pytest.raises(LookupUnavailable):
        openlibrary.search_author("Ursula K. Le Guin")


def test_author_search_raises_lookup_unavailable_on_a_non_object_payload(
    mock_openlibrary,
) -> None:
    mock_openlibrary(json_route(["not", "an", "object"]))

    with pytest.raises(LookupUnavailable):
        openlibrary.search_author("Ursula K. Le Guin")


# --------------------------------------------------------------------------
# Backend selection and the seed fallback
# --------------------------------------------------------------------------


def test_the_seed_finds_every_book_by_an_author() -> None:
    page = lookup_module.search_seed_author("Tolkien")

    assert [book.title for book in page.results] == [
        "The Hobbit",
        "The Lord of the Rings",
    ]
    assert page.total == 2


def test_the_seed_ranks_an_exact_author_before_a_partial_one() -> None:
    page = lookup_module.search_seed_author("J. R. R. Tolkien")

    assert len(page.results) == 2
    assert all(book.author == "J. R. R. Tolkien" for book in page.results)


def test_the_seed_returns_nothing_for_a_blank_author() -> None:
    assert lookup_module.search_seed_author("   ").results == []


def test_the_seed_backend_answers_the_author_search(monkeypatch) -> None:
    monkeypatch.setenv(lookup_module.BACKEND_ENV, lookup_module.SEED_BACKEND)

    page = lookup_module.search_author("George Orwell")

    assert page.results[0].title == "Nineteen Eighty-Four"


def test_the_author_search_falls_back_to_the_seed_when_open_library_is_down(
    mock_openlibrary,
) -> None:
    mock_openlibrary(json_route({"docs": []}, status_code=503))

    page = lookup_module.search_author("George Orwell")

    assert [book.title for book in page.results] == ["Nineteen Eighty-Four"]


def test_the_author_search_falls_back_to_the_seed_when_the_catalogue_is_empty(
    mock_openlibrary,
) -> None:
    mock_openlibrary(json_route({"numFound": 0, "docs": []}))

    page = lookup_module.search_author("George Orwell")

    assert [book.title for book in page.results] == ["Nineteen Eighty-Four"]


def test_the_mcp_backend_answers_the_author_search(monkeypatch) -> None:
    expected = details("Author Tool Edition", "Tool Author", "9780000000003")
    seen: list[str] = []

    def search(author: str, *, limit: int = 5, offset: int = 0) -> SearchPage:
        seen.append(author)
        return SearchPage(results=[expected], total=1)

    monkeypatch.setenv(lookup_module.BACKEND_ENV, lookup_module.MCP_BACKEND)
    monkeypatch.setattr(mcp_client, "search_author", search)

    assert lookup_module.search_author("Tool Author").results == [expected]
    assert seen == ["Tool Author"]


def test_the_author_search_falls_back_to_the_seed_when_mcp_is_unavailable(
    monkeypatch,
) -> None:
    def unavailable(author: str, *, limit: int = 5, offset: int = 0):
        raise mcp_client.MCPUnavailable("server is down")

    monkeypatch.setenv(lookup_module.BACKEND_ENV, lookup_module.MCP_BACKEND)
    monkeypatch.setattr(mcp_client, "search_author", unavailable)

    page = lookup_module.search_author("George Orwell")

    assert [book.title for book in page.results] == ["Nineteen Eighty-Four"]


# --------------------------------------------------------------------------
# The MCP tool and its application-side client
# --------------------------------------------------------------------------


def call_author_tool(author: str, **arguments):
    """Call the registered MCP tool and return its complete protocol result."""

    async def call():
        async with Client(server.mcp) as client:
            return await client.call_tool(
                "search_by_author",
                {"author": author, **arguments},
                raise_on_error=False,
            )

    return asyncio.run(call())


def author_tool_text(author: str, **arguments) -> str:
    return call_author_tool(author, **arguments).content[0].text


def test_the_author_tool_returns_readable_normalized_results(monkeypatch) -> None:
    monkeypatch.setattr(
        server,
        "search_open_library_author",
        one_page(
            BookDetails(
                title="A Wizard of Earthsea",
                author="Ursula K. Le Guin",
                isbn="9780553262506",
                year=1968,
                cover_url="https://covers.example/earthsea.jpg",
            )
        ),
    )

    text = author_tool_text("  Ursula K. Le Guin  ")

    assert text.startswith('Found 1 books written by "Ursula K. Le Guin":')
    assert "1. A Wizard of Earthsea" in text
    assert "Author: Ursula K. Le Guin" in text
    assert "First published: 1968" in text

    structured = call_author_tool("Ursula K. Le Guin").structured_content
    assert structured["status"] == "ok"
    assert structured["total"] == 1
    assert structured["books"][0]["isbn"] == "9780553262506"


def test_the_author_tool_says_how_many_more_matches_exist(monkeypatch) -> None:
    monkeypatch.setattr(
        server,
        "search_open_library_author",
        one_page(details("Harry Potter", "J. K. Rowling", "9780261103344"), total=421),
    )

    text = author_tool_text("J. K. Rowling")

    assert 'Found 421 books written by "J. K. Rowling", showing 1' in text


def test_the_author_tool_rejects_a_blank_name_without_a_lookup(monkeypatch) -> None:
    def fail_if_called(author: str, *, limit: int = 5, offset: int = 0):
        raise AssertionError("blank input must not call Open Library")

    monkeypatch.setattr(server, "search_open_library_author", fail_if_called)

    assert author_tool_text("   ") == "Error: author must not be blank."


def test_the_author_tool_rejects_an_overlong_name_without_a_lookup(
    monkeypatch,
) -> None:
    def fail_if_called(author: str, *, limit: int = 5, offset: int = 0):
        raise AssertionError("overlong input must not call Open Library")

    monkeypatch.setattr(server, "search_open_library_author", fail_if_called)

    text = author_tool_text("x" * (server.MAX_AUTHOR_LENGTH + 1))

    assert text == "Error: author must be 300 characters or fewer."


def test_the_author_tool_rejects_paging_it_cannot_serve(monkeypatch) -> None:
    def fail_if_called(author: str, *, limit: int = 5, offset: int = 0):
        raise AssertionError("invalid paging must not call Open Library")

    monkeypatch.setattr(server, "search_open_library_author", fail_if_called)

    assert author_tool_text("Le Guin", limit=0) == (
        f"Error: limit must be between 1 and {server.MAX_RESULTS}."
    )
    assert author_tool_text("Le Guin", limit=server.MAX_RESULTS + 1) == (
        f"Error: limit must be between 1 and {server.MAX_RESULTS}."
    )
    assert author_tool_text("Le Guin", offset=-1) == (
        "Error: offset must not be negative."
    )


def test_the_author_tool_reports_no_matches(monkeypatch) -> None:
    monkeypatch.setattr(server, "search_open_library_author", one_page())

    assert author_tool_text("Nobody At All") == (
        'No books found written by "Nobody At All".'
    )


def test_the_author_tool_hides_catalogue_failures_from_the_client(
    monkeypatch,
) -> None:
    def unavailable(author: str, *, limit: int = 5, offset: int = 0):
        raise LookupUnavailable("internal network details")

    monkeypatch.setattr(server, "search_open_library_author", unavailable)

    text = author_tool_text("Ursula K. Le Guin")

    assert text == (
        "Open Library is temporarily unavailable. "
        "Please try this book search again later."
    )
    assert "internal network details" not in text


def test_the_client_converts_author_tool_results_to_book_details(
    monkeypatch,
) -> None:
    expected = BookDetails(
        title="A Wizard of Earthsea",
        author="Ursula K. Le Guin",
        isbn="9780553262506",
        year=1968,
    )
    monkeypatch.setattr(
        server, "search_open_library_author", one_page(expected, total=257)
    )

    page = mcp_client.search_author("Ursula K. Le Guin")

    assert page.results == [expected]
    assert page.total == 257


def test_the_client_returns_an_empty_page_when_no_author_matched(
    monkeypatch,
) -> None:
    monkeypatch.setattr(server, "search_open_library_author", one_page())

    assert mcp_client.search_author("Nobody At All").results == []


def test_the_client_maps_an_author_tool_failure_to_mcp_unavailable(
    monkeypatch,
) -> None:
    def unavailable(author: str, *, limit: int = 5, offset: int = 0):
        raise LookupUnavailable("internal network details")

    monkeypatch.setattr(server, "search_open_library_author", unavailable)

    with pytest.raises(mcp_client.MCPUnavailable):
        mcp_client.search_author("Ursula K. Le Guin")


# --------------------------------------------------------------------------
# The search service
# --------------------------------------------------------------------------


def test_the_author_service_returns_the_authors_books(monkeypatch) -> None:
    monkeypatch.setattr(
        search_service,
        "search_author",
        one_page(details("Nineteen Eighty-Four", "George Orwell", "9780451524935")),
    )

    page = search_service.by_author("George Orwell")

    assert [book.title for book in page.candidates] == ["Nineteen Eighty-Four"]


def test_the_author_service_still_answers_when_the_catalogue_fails(
    monkeypatch,
) -> None:
    def explode(query: str, *, limit: int = 5, offset: int = 0):
        raise RuntimeError("the catalogue is unreachable")

    monkeypatch.setattr(search_service, "search_author", explode)

    page = search_service.by_author("George Orwell")

    assert page.candidates == []
    assert page.total == 0


def test_candidates_without_an_isbn_are_never_offered(monkeypatch) -> None:
    monkeypatch.setattr(
        search_service,
        "search_author",
        one_page(
            BookDetails(title="No ISBN", author="George Orwell"),
            details("Nineteen Eighty-Four", "George Orwell", "9780451524935"),
        ),
    )

    page = search_service.by_author("George Orwell")

    assert [book.title for book in page.candidates] == ["Nineteen Eighty-Four"]


# --------------------------------------------------------------------------
# The HTTP endpoints
# --------------------------------------------------------------------------


def test_searching_an_author_name_returns_their_books(client) -> None:
    """The bug this feature fixes, end to end on the seed."""
    response = client.get("/books/search", params={"author": "George Orwell"})

    assert response.status_code == 200
    assert [book["title"] for book in response.json()["items"]] == [
        "Nineteen Eighty-Four"
    ]


def test_searching_an_author_surname_returns_all_their_books(client) -> None:
    response = client.get("/books/search", params={"author": "Tolkien"})

    assert response.status_code == 200
    assert [book["title"] for book in response.json()["items"]] == [
        "The Hobbit",
        "The Lord of the Rings",
    ]


def test_the_title_index_does_not_answer_an_author_name(client) -> None:
    """Why the author index is needed: the seeded titles contain no author names."""
    response = client.get("/books/search", params={"title": "Tolkien"})

    assert response.status_code == 200
    assert response.json()["items"] == []


def test_a_search_must_choose_one_index(client) -> None:
    for params in ({}, {"title": "The Hobbit", "author": "Tolkien"}):
        response = client.get("/books/search", params=params)

        assert response.status_code == 422
        assert response.json()["detail"] == "Provide exactly one of title or author."


def test_searching_stores_nothing(client) -> None:
    client.get("/books/search", params={"author": "George Orwell"})

    assert client.get("/books").json() == []


def test_a_book_found_by_author_can_be_added(client) -> None:
    candidates = client.get(
        "/books/search", params={"author": "George Orwell"}
    ).json()["items"]

    response = client.post(
        "/books",
        json={
            "title": candidates[0]["title"],
            "isbn": candidates[0]["isbn"],
            "shelf": "wishlist",
        },
    )

    assert response.status_code == 201
    book = response.json()
    assert book["title"] == "Nineteen Eighty-Four"
    assert book["author"] == "George Orwell"
    assert book["shelf"] == "wishlist"
    assert book["details_pending"] is False
