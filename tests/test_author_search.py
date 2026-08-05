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
from app.details import BookDetails
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
    """A minimal catalogue result for the merge and endpoint tests."""
    return BookDetails(title=title, author=author, isbn=isbn)


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
    openlibrary.search_author("  Ursula K. Le Guin  ")

    assert seen["path"] == "/search.json"
    assert seen["author"] == "Ursula K. Le Guin"
    assert "title" not in seen
    assert seen["fields"] == openlibrary.SEARCH_FIELDS


def test_author_search_maps_the_authors_own_books(mock_openlibrary) -> None:
    mock_openlibrary(json_route(LE_GUIN))

    results = openlibrary.search_author("Ursula K. Le Guin")

    assert [book.title for book in results] == [
        "A Wizard of Earthsea",
        "The Left Hand of Darkness",
    ]
    first = results[0]
    assert first.author == "Ursula K. Le Guin"
    assert first.year == 1968
    assert first.isbn == "9780553262506"  # the 13-digit one, not the first listed
    assert first.cover_url == "https://covers.openlibrary.org/b/id/8231990-M.jpg"


def test_author_search_drops_an_anthology_credited_to_someone_else(
    mock_openlibrary,
) -> None:
    mock_openlibrary(json_route(LE_GUIN))

    titles = [book.title for book in openlibrary.search_author("Ursula K. Le Guin")]

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

    results = openlibrary.search_author("J. R. R. Tolkien")

    assert [book.title for book in results] == ["The Hobbit"]


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

    results = openlibrary.search_author("Ted Chiang")

    assert [book.title for book in results] == ["Vanishing Acts"]


def test_author_search_returns_nothing_for_a_blank_name_without_a_request(
    mock_openlibrary,
) -> None:
    def fail_if_called(request: httpx.Request) -> httpx.Response:
        raise AssertionError("a blank author must not reach Open Library")

    mock_openlibrary(fail_if_called)

    assert openlibrary.search_author("   ") == []


def test_author_search_returns_nothing_when_the_catalogue_has_no_docs(
    mock_openlibrary,
) -> None:
    mock_openlibrary(json_route({"numFound": 0, "docs": []}))

    assert openlibrary.search_author("Nobody At All") == []


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
    results = lookup_module.search_seed_author("Tolkien")

    assert [book.title for book in results] == [
        "The Hobbit",
        "The Lord of the Rings",
    ]


def test_the_seed_ranks_an_exact_author_before_a_partial_one() -> None:
    results = lookup_module.search_seed_author("J. R. R. Tolkien")

    assert len(results) == 2
    assert all(book.author == "J. R. R. Tolkien" for book in results)


def test_the_seed_returns_nothing_for_a_blank_author() -> None:
    assert lookup_module.search_seed_author("   ") == []


def test_the_seed_backend_answers_the_author_search(monkeypatch) -> None:
    monkeypatch.setenv(lookup_module.BACKEND_ENV, lookup_module.SEED_BACKEND)

    assert lookup_module.search_author("George Orwell")[0].title == (
        "Nineteen Eighty-Four"
    )


def test_the_author_search_falls_back_to_the_seed_when_open_library_is_down(
    mock_openlibrary,
) -> None:
    mock_openlibrary(json_route({"docs": []}, status_code=503))

    results = lookup_module.search_author("George Orwell")

    assert [book.title for book in results] == ["Nineteen Eighty-Four"]


def test_the_author_search_falls_back_to_the_seed_when_the_catalogue_is_empty(
    mock_openlibrary,
) -> None:
    mock_openlibrary(json_route({"numFound": 0, "docs": []}))

    results = lookup_module.search_author("George Orwell")

    assert [book.title for book in results] == ["Nineteen Eighty-Four"]


def test_the_mcp_backend_answers_the_author_search(monkeypatch) -> None:
    expected = details("Author Tool Edition", "Tool Author", "9780000000003")
    seen: list[str] = []

    def search(author: str) -> list[BookDetails]:
        seen.append(author)
        return [expected]

    monkeypatch.setenv(lookup_module.BACKEND_ENV, lookup_module.MCP_BACKEND)
    monkeypatch.setattr(mcp_client, "search_by_author", search)

    assert lookup_module.search_author("Tool Author") == [expected]
    assert seen == ["Tool Author"]


def test_the_author_search_falls_back_to_the_seed_when_mcp_is_unavailable(
    monkeypatch,
) -> None:
    def unavailable(author: str):
        raise mcp_client.MCPUnavailable("server is down")

    monkeypatch.setenv(lookup_module.BACKEND_ENV, lookup_module.MCP_BACKEND)
    monkeypatch.setattr(mcp_client, "search_by_author", unavailable)

    results = lookup_module.search_author("George Orwell")

    assert [book.title for book in results] == ["Nineteen Eighty-Four"]


# --------------------------------------------------------------------------
# The MCP tool and its application-side client
# --------------------------------------------------------------------------


def call_author_tool(author: str):
    """Call the registered MCP tool and return its complete protocol result."""

    async def call():
        async with Client(server.mcp) as client:
            return await client.call_tool(
                "search_by_author",
                {"author": author},
                raise_on_error=False,
            )

    return asyncio.run(call())


def author_tool_text(author: str) -> str:
    return call_author_tool(author).content[0].text


def test_the_author_tool_returns_readable_normalized_results(monkeypatch) -> None:
    monkeypatch.setattr(
        server,
        "search_open_library_author",
        lambda author: [
            BookDetails(
                title="A Wizard of Earthsea",
                author="Ursula K. Le Guin",
                isbn="9780553262506",
                year=1968,
                cover_url="https://covers.example/earthsea.jpg",
            )
        ],
    )

    text = author_tool_text("  Ursula K. Le Guin  ")

    assert text.startswith('Found 1 books written by "Ursula K. Le Guin":')
    assert "1. A Wizard of Earthsea" in text
    assert "Author: Ursula K. Le Guin" in text
    assert "First published: 1968" in text

    structured = call_author_tool("Ursula K. Le Guin").structured_content
    assert structured["status"] == "ok"
    assert structured["books"][0]["isbn"] == "9780553262506"


def test_the_author_tool_rejects_a_blank_name_without_a_lookup(monkeypatch) -> None:
    def fail_if_called(author: str):
        raise AssertionError("blank input must not call Open Library")

    monkeypatch.setattr(server, "search_open_library_author", fail_if_called)

    assert author_tool_text("   ") == "Error: author must not be blank."


def test_the_author_tool_rejects_an_overlong_name_without_a_lookup(
    monkeypatch,
) -> None:
    def fail_if_called(author: str):
        raise AssertionError("overlong input must not call Open Library")

    monkeypatch.setattr(server, "search_open_library_author", fail_if_called)

    text = author_tool_text("x" * (server.MAX_AUTHOR_LENGTH + 1))

    assert text == "Error: author must be 300 characters or fewer."


def test_the_author_tool_reports_no_matches(monkeypatch) -> None:
    monkeypatch.setattr(server, "search_open_library_author", lambda author: [])

    assert author_tool_text("Nobody At All") == (
        'No books found written by "Nobody At All".'
    )


def test_the_author_tool_hides_catalogue_failures_from_the_client(
    monkeypatch,
) -> None:
    def unavailable(author: str):
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
        server, "search_open_library_author", lambda author: [expected]
    )

    assert mcp_client.search_by_author("Ursula K. Le Guin") == [expected]


def test_the_client_returns_an_empty_list_when_no_author_matched(
    monkeypatch,
) -> None:
    monkeypatch.setattr(server, "search_open_library_author", lambda author: [])

    assert mcp_client.search_by_author("Nobody At All") == []


def test_the_client_maps_an_author_tool_failure_to_mcp_unavailable(
    monkeypatch,
) -> None:
    def unavailable(author: str):
        raise LookupUnavailable("internal network details")

    monkeypatch.setattr(server, "search_open_library_author", unavailable)

    with pytest.raises(mcp_client.MCPUnavailable):
        mcp_client.search_by_author("Ursula K. Le Guin")


# --------------------------------------------------------------------------
# Merging the two searches behind one search box
# --------------------------------------------------------------------------


def test_a_title_search_labels_its_candidates(monkeypatch) -> None:
    monkeypatch.setattr(
        search_service,
        "search_book",
        lambda title: [details("The Hobbit", "Tolkien", "9780261103344")],
    )

    candidates = search_service.by_title("The Hobbit")

    assert [candidate.matched for candidate in candidates] == ["title"]


def test_an_author_search_labels_its_candidates(monkeypatch) -> None:
    monkeypatch.setattr(
        search_service,
        "search_author",
        lambda author: [details("Nineteen Eighty-Four", "Orwell", "9780451524935")],
    )

    candidates = search_service.by_author("George Orwell")

    assert [candidate.matched for candidate in candidates] == ["author"]


def test_one_query_interleaves_both_searches_starting_with_the_title(
    monkeypatch,
) -> None:
    """The cap is why: title results alone would fill every slot."""
    monkeypatch.setattr(
        search_service,
        "search_book",
        lambda query: [
            details(f"About Orwell {index}", "A Biographer", f"111111111{index}")
            for index in range(5)
        ],
    )
    monkeypatch.setattr(
        search_service,
        "search_author",
        lambda query: [
            details(f"By Orwell {index}", "George Orwell", f"222222222{index}")
            for index in range(5)
        ],
    )

    candidates = search_service.by_query("George Orwell")

    assert [candidate.matched for candidate in candidates] == [
        "title",
        "author",
        "title",
        "author",
        "title",
    ]
    assert [candidate.details.title for candidate in candidates] == [
        "About Orwell 0",
        "By Orwell 0",
        "About Orwell 1",
        "By Orwell 1",
        "About Orwell 2",
    ]


def test_a_surname_shared_with_a_famous_title_does_not_take_a_slot(
    monkeypatch,
) -> None:
    """Searching "Dune" finds authors named Dune. Their books are not the ask."""
    monkeypatch.setattr(
        search_service,
        "search_book",
        lambda query: [
            details(f"{name} Dune", "Frank Herbert", f"111111111{index}")
            for index, name in enumerate(
                ["Children of", "Chapterhouse", "Heretics of", "God Emperor of", "The"]
            )
        ],
    )
    monkeypatch.setattr(
        search_service,
        "search_author",
        lambda query: [
            details("Barron's TEAS practice tests", "Linda Dune", "2222222220"),
            details("999", "Heather Dune Macadam", "2222222221"),
        ],
    )

    candidates = search_service.by_query("Dune")

    assert [candidate.matched for candidate in candidates] == ["title"] * 5
    assert all("Dune" in candidate.details.title for candidate in candidates)


def test_a_partial_author_match_still_appears_when_titles_leave_room(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        search_service,
        "search_book",
        lambda query: [details("Tolkien: A Biography", "H. Carpenter", "1111111111")],
    )
    monkeypatch.setattr(
        search_service,
        "search_author",
        lambda query: [details("The Hobbit", "J.R.R. Tolkien", "9780261103344")],
    )

    candidates = search_service.by_query("Tolkien")

    assert [candidate.matched for candidate in candidates] == ["title", "author"]
    assert candidates[1].details.title == "The Hobbit"


def test_a_full_name_typed_with_spaced_initials_takes_a_slot(monkeypatch) -> None:
    """The query "J. R. R. Tolkien" must reach the catalogue's "J.R.R. Tolkien"."""
    monkeypatch.setattr(
        search_service,
        "search_book",
        lambda query: [
            details(f"About Tolkien {index}", "A Biographer", f"111111111{index}")
            for index in range(5)
        ],
    )
    monkeypatch.setattr(
        search_service,
        "search_author",
        lambda query: [details("The Hobbit", "J.R.R. Tolkien", "9780261103344")],
    )

    candidates = search_service.by_query("J. R. R. Tolkien")

    assert candidates[1].matched == "author"
    assert candidates[1].details.title == "The Hobbit"


def test_a_name_missing_a_middle_initial_still_takes_a_slot(monkeypatch) -> None:
    monkeypatch.setattr(
        search_service,
        "search_book",
        lambda query: [
            details(f"About Le Guin {index}", "H. Bloom", f"111111111{index}")
            for index in range(5)
        ],
    )
    monkeypatch.setattr(
        search_service,
        "search_author",
        lambda query: [
            details("A Wizard of Earthsea", "Ursula K. Le Guin", "9780553262506")
        ],
    )

    candidates = search_service.by_query("Ursula Le Guin")

    assert candidates[1].matched == "author"


def test_the_explicit_author_parameter_is_not_second_guessed(monkeypatch) -> None:
    """A caller who says "author" has already decided; do not demote anything."""
    monkeypatch.setattr(
        search_service,
        "search_author",
        lambda author: [
            details("Barron's TEAS practice tests", "Linda Dune", "2222222220")
        ],
    )

    candidates = search_service.by_author("Dune")

    assert [candidate.matched for candidate in candidates] == ["author"]


def test_one_query_offers_a_book_found_by_both_searches_only_once(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        search_service,
        "search_book",
        lambda query: [details("Dune", "Frank Herbert", "978-0-441-01359-3")],
    )
    monkeypatch.setattr(
        search_service,
        "search_author",
        lambda query: [details("Dune", "Frank Herbert", "9780441013593")],
    )

    candidates = search_service.by_query("Dune")

    assert len(candidates) == 1
    assert candidates[0].details.isbn == "9780441013593"
    assert candidates[0].matched == "title"  # whichever search ranked it sooner


def test_one_query_still_answers_when_one_search_fails(monkeypatch) -> None:
    def explode(query: str):
        raise RuntimeError("the catalogue is unreachable")

    monkeypatch.setattr(search_service, "search_book", explode)
    monkeypatch.setattr(
        search_service,
        "search_author",
        lambda query: [details("Nineteen Eighty-Four", "Orwell", "9780451524935")],
    )

    candidates = search_service.by_query("George Orwell")

    assert [candidate.matched for candidate in candidates] == ["author"]


def test_candidates_without_an_isbn_are_never_offered(monkeypatch) -> None:
    monkeypatch.setattr(
        search_service,
        "search_author",
        lambda author: [
            BookDetails(title="No ISBN", author="George Orwell"),
            details("Nineteen Eighty-Four", "George Orwell", "9780451524935"),
        ],
    )

    candidates = search_service.by_author("George Orwell")

    assert [candidate.details.title for candidate in candidates] == [
        "Nineteen Eighty-Four"
    ]


# --------------------------------------------------------------------------
# The HTTP endpoints
# --------------------------------------------------------------------------


def test_searching_an_author_name_returns_their_books(client) -> None:
    """The bug this feature fixes, end to end on the seed."""
    response = client.get("/books/search", params={"q": "George Orwell"})

    assert response.status_code == 200
    assert [book["title"] for book in response.json()] == ["Nineteen Eighty-Four"]
    assert response.json()[0]["matched"] == "author"


def test_searching_a_title_is_unchanged_and_labelled_as_a_title_match(
    client,
) -> None:
    response = client.get("/books/search", params={"q": "The Hobbit"})

    assert response.status_code == 200
    assert response.json()[0]["title"] == "The Hobbit"
    assert response.json()[0]["matched"] == "title"


def test_the_author_parameter_searches_only_authors(client) -> None:
    response = client.get("/books/search", params={"author": "Tolkien"})

    assert response.status_code == 200
    assert [book["title"] for book in response.json()] == [
        "The Hobbit",
        "The Lord of the Rings",
    ]
    assert {book["matched"] for book in response.json()} == {"author"}


def test_the_title_parameter_still_searches_only_titles(client) -> None:
    response = client.get("/books/search", params={"title": "Tolkien"})

    assert response.status_code == 200
    assert response.json() == []


def test_a_search_with_no_parameters_is_rejected(client) -> None:
    response = client.get("/books/search")

    assert response.status_code == 422
    assert response.json()["detail"] == "Provide q, title, or author."


def test_searching_stores_nothing(client) -> None:
    client.get("/books/search", params={"q": "George Orwell"})

    assert client.get("/books").json() == []


def test_a_book_found_by_author_can_be_added(client) -> None:
    response = client.post(
        "/books",
        json={
            "title": "Nineteen Eighty-Four",
            "query": "George Orwell",
            "isbn": "9780451524935",
            "shelf": "wishlist",
        },
    )

    assert response.status_code == 201
    book = response.json()
    assert book["title"] == "Nineteen Eighty-Four"
    assert book["author"] == "George Orwell"
    assert book["shelf"] == "wishlist"
    assert book["details_pending"] is False


def test_adding_a_book_found_by_author_needs_the_query_that_found_it(
    client,
) -> None:
    """Without ``query`` the server re-searches by title and cannot confirm it."""
    response = client.post(
        "/books",
        json={"title": "George Orwell", "isbn": "9780451524935"},
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "isbn_not_found"
    assert client.get("/books").json() == []


def test_a_submitted_isbn_must_be_one_the_search_actually_returned(client) -> None:
    """The re-search is what stops a client inventing metadata for an ISBN."""
    response = client.post(
        "/books",
        json={
            "title": "Nineteen Eighty-Four",
            "query": "George Orwell",
            "isbn": "9999999999999",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "isbn_not_found"


def test_a_blank_query_falls_back_to_the_title_search(client) -> None:
    response = client.post(
        "/books",
        json={"title": "The Hobbit", "query": "   ", "isbn": "9780261103344"},
    )

    assert response.status_code == 201
    assert response.json()["title"] == "The Hobbit"
