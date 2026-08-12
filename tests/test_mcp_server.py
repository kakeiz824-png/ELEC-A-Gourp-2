"""MCP tool tests using FastMCP's in-memory client.

The Open Library function is replaced in every call, so these tests never
access the network.
"""

import asyncio
import logging
from pathlib import Path
import sys

from fastmcp import Client
from fastmcp.client.transports import StdioTransport

from app.details import AuthorDetails, BookDetails, SearchPage
from app.openlibrary import LookupUnavailable
from mcp_server import server


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def call_search_result(title: str):
    """Call the registered MCP tool and return its complete protocol result."""

    async def call():
        async with Client(server.mcp) as client:
            return await client.call_tool(
                "search_book",
                {"title": title},
                raise_on_error=False,
            )

    return asyncio.run(call())


def call_search_book(title: str) -> str:
    """Call the registered MCP tool and return its readable text content."""
    return call_search_result(title).content[0].text


def call_get_book_details(isbn: str):
    """Call the registered ISBN tool and return its complete protocol result."""

    async def call():
        async with Client(server.mcp) as client:
            return await client.call_tool(
                "get_book_details",
                {"isbn": isbn},
                raise_on_error=False,
            )

    return asyncio.run(call())


def call_details_text(isbn: str) -> str:
    """Call the registered ISBN tool and return its readable text content."""
    return call_get_book_details(isbn).content[0].text


def call_get_author_details(name: str):
    """Call the registered author tool and return its complete protocol result."""

    async def call():
        async with Client(server.mcp) as client:
            return await client.call_tool(
                "get_author_details",
                {"name": name},
                raise_on_error=False,
            )

    return asyncio.run(call())


def test_server_registers_both_searches_with_ai_facing_descriptions() -> None:
    async def list_tools():
        async with Client(server.mcp) as client:
            return await client.list_tools()

    tools = asyncio.run(list_tools())
    described = {tool.name: tool.description for tool in tools}

    assert sorted(described) == [
        "find_similar_books",
        "get_author_details",
        "get_book_details",
        "search_book",
        "search_by_author",
        "search_by_subject",
    ]
    for description in described.values():
        assert "Use this tool when" in description


def test_server_starts_over_stdio_like_a_desktop_mcp_client() -> None:
    async def list_tools():
        transport = StdioTransport(
            command=sys.executable,
            args=["-m", "mcp_server.server"],
            cwd=str(PROJECT_ROOT),
        )
        async with Client(transport) as client:
            return await client.list_tools()

    tools = asyncio.run(list_tools())

    assert sorted(tool.name for tool in tools) == [
        "find_similar_books",
        "get_author_details",
        "get_book_details",
        "search_book",
        "search_by_author",
        "search_by_subject",
    ]


def test_search_book_returns_readable_normalized_results(monkeypatch) -> None:
    results = [
        BookDetails(
            title="The Hobbit",
            author="J.R.R. Tolkien",
            isbn="9780261103344",
            year=1937,
            cover_url="https://covers.example/hobbit.jpg",
        ),
        BookDetails(title="The Hobbit: Graphic Novel", author="Chuck Dixon"),
    ]
    monkeypatch.setattr(
        server,
        "search_open_library",
        lambda title, **paging: SearchPage(results=results, total=len(results)),
    )

    text = call_search_book("  The Hobbit  ")

    assert text.startswith('Found 2 books matching "The Hobbit":')
    assert "1. The Hobbit" in text
    assert "Author: J.R.R. Tolkien" in text
    assert "First published: 1937" in text
    assert "ISBN: 9780261103344" in text
    assert "2. The Hobbit: Graphic Novel" in text
    assert "ISBN: Unknown" in text

    structured = call_search_result("The Hobbit").structured_content
    assert structured["status"] == "ok"
    assert structured["books"][0] == {
        "title": "The Hobbit",
        "author": "J.R.R. Tolkien",
        "isbn": "9780261103344",
        "year": 1937,
        "cover_url": "https://covers.example/hobbit.jpg",
    }


def test_search_book_rejects_a_blank_title_without_a_lookup(monkeypatch) -> None:
    def fail_if_called(title: str, **paging):
        raise AssertionError("blank input must not call Open Library")

    monkeypatch.setattr(server, "search_open_library", fail_if_called)

    assert call_search_book("   ") == "Error: title must not be blank."


def test_search_book_rejects_an_overlong_title_without_a_lookup(monkeypatch) -> None:
    def fail_if_called(title: str, **paging):
        raise AssertionError("overlong input must not call Open Library")

    monkeypatch.setattr(server, "search_open_library", fail_if_called)

    text = call_search_book("x" * (server.MAX_TITLE_LENGTH + 1))

    assert text == "Error: title must be 300 characters or fewer."


def test_search_book_reports_no_matches(monkeypatch) -> None:
    monkeypatch.setattr(
        server, "search_open_library", lambda title, **paging: SearchPage([], 0)
    )

    assert (
        call_search_book("A Missing Book")
        == 'No books found matching "A Missing Book".'
    )


def test_search_book_hides_catalogue_failures_from_the_client(monkeypatch) -> None:
    def unavailable(title: str, **paging):
        raise LookupUnavailable("internal network details")

    monkeypatch.setattr(server, "search_open_library", unavailable)

    text = call_search_book("The Hobbit")

    assert text == (
        "Open Library is temporarily unavailable. "
        "Please try this book search again later."
    )
    assert "internal network details" not in text

def test_search_book_hides_unexpected_exceptions_from_the_client(
    monkeypatch,
) -> None:
    """An unexpected bug must look like an outage, and stay out of client text."""

    def explode(title: str, **paging):
        raise RuntimeError("internal mapping bug")

    monkeypatch.setattr(server, "search_open_library", explode)

    result = call_search_result("The Hobbit")

    assert result.structured_content == {
        "status": "unavailable",
        "books": [],
        "total": 0,
    }
    text = result.content[0].text
    assert "internal mapping bug" not in text
    assert "temporarily unavailable" in text


def test_search_book_logs_the_unexpected_exception_for_diagnostics(
    monkeypatch, caplog
) -> None:
    """The internal detail is logged server-side, never shown to the client."""

    def explode(title: str, **paging):
        raise RuntimeError("internal mapping bug")

    monkeypatch.setattr(server, "search_open_library", explode)
    caplog.set_level(logging.ERROR, logger="mcp_server.server")

    call_search_result("The Hobbit")

    assert "internal mapping bug" in caplog.text

def call_search_by_author(author: str) -> str:
    """Call the registered author tool and return its readable text content."""

    async def call():
        async with Client(server.mcp) as client:
            return await client.call_tool(
                "search_by_author",
                {"author": author},
                raise_on_error=False,
            )

    return asyncio.run(call()).content[0].text


def test_search_book_collapses_whitespace_and_drops_control_characters(
    monkeypatch,
) -> None:
    """Newlines, tabs, repeated spaces and NBSP reach the search single-spaced."""
    received: dict[str, str] = {}

    def record(title: str, **paging):
        received["query"] = title
        return SearchPage([], 0)

    monkeypatch.setattr(server, "search_open_library", record)

    call_search_book("  The\u00a0Hobbit\n\n  \tPart   One!  ")

    assert received["query"] == "The Hobbit Part One!"


def test_search_book_rejects_control_characters_only(monkeypatch) -> None:
    def fail_if_called(title: str, **paging):
        raise AssertionError("control-only input must not call Open Library")

    monkeypatch.setattr(server, "search_open_library", fail_if_called)

    assert (
        call_search_book("\x00\x01\x02\x1f") == "Error: title must not be blank."
    )


def test_the_length_limit_is_measured_after_normalisation(monkeypatch) -> None:
    received: dict[str, str] = {}

    def record(title: str, **paging):
        received["query"] = title
        return SearchPage([], 0)

    monkeypatch.setattr(server, "search_open_library", record)

    call_search_book("The" + " " * (server.MAX_TITLE_LENGTH + 100) + "Hobbit")

    assert received["query"] == "The Hobbit"


def test_search_book_keeps_title_punctuation(monkeypatch) -> None:
    received: dict[str, str] = {}

    def record(title: str, **paging):
        received["query"] = title
        return SearchPage([], 0)

    monkeypatch.setattr(server, "search_open_library", record)

    call_search_book("Dune: Part 'One' & Two.")

    assert received["query"] == "Dune: Part 'One' & Two."


def test_both_search_tools_normalise_identically(monkeypatch) -> None:
    received: dict[str, str] = {}

    def record_title(title: str, **paging):
        received["title"] = title
        return SearchPage([], 0)

    def record_author(author: str, **paging):
        received["author"] = author
        return SearchPage([], 0)

    monkeypatch.setattr(server, "search_open_library", record_title)
    monkeypatch.setattr(server, "search_open_library_author", record_author)

    call_search_book("  J.\nK.\t Rowling  ")
    call_search_by_author("  J.\nK.\t Rowling  ")

    assert received["title"] == "J. K. Rowling"
    assert received["author"] == "J. K. Rowling"

def test_readable_and_structured_outputs_share_one_field_set() -> None:
    """A field added to one rendering must appear in the other."""

    book = BookDetails(
        title="The Hobbit",
        author="J.R.R. Tolkien",
        isbn="9780261103344",
        year=1937,
        cover_url="https://covers.example/hobbit.jpg",
    )

    payload = server._book_payload(book)
    lines = server._format_book(1, book).splitlines()

    labels = {
        "Author": "author",
        "First published": "year",
        "ISBN": "isbn",
        "Cover": "cover_url",
    }
    names = {"title"}
    for line in lines:
        label, _, _ = line.strip().partition(": ")
        if label in labels:
            names.add(labels[label])

    assert names == set(payload)
    assert len(lines) == len(payload)


def test_get_book_details_returns_a_normalized_result(monkeypatch) -> None:
    details = BookDetails(
        title="The Hobbit",
        author="J.R.R. Tolkien",
        isbn="9780261103344",
        year=1937,
        cover_url="https://covers.example/hobbit.jpg",
    )
    monkeypatch.setattr(server, "open_library_details", lambda isbn: details)

    text = call_details_text("9780261103344")

    assert text.startswith("Found ISBN 9780261103344:")
    assert "The Hobbit" in text
    assert "Author: J.R.R. Tolkien" in text
    assert "First published: 1937" in text
    assert "Cover: https://covers.example/hobbit.jpg" in text

    structured = call_get_book_details("9780261103344").structured_content
    assert structured["status"] == "ok"
    assert structured["book"] == {
        "title": "The Hobbit",
        "author": "J.R.R. Tolkien",
        "isbn": "9780261103344",
        "year": 1937,
        "cover_url": "https://covers.example/hobbit.jpg",
    }


def test_get_book_details_rejects_a_blank_isbn_without_a_lookup(monkeypatch) -> None:
    def fail_if_called(isbn: str):
        raise AssertionError("blank input must not call Open Library")

    monkeypatch.setattr(server, "open_library_details", fail_if_called)

    assert call_details_text("   ") == "Error: isbn must not be blank."


def test_get_book_details_rejects_an_overlong_isbn_without_a_lookup(monkeypatch) -> None:
    def fail_if_called(isbn: str):
        raise AssertionError("overlong input must not call Open Library")

    monkeypatch.setattr(server, "open_library_details", fail_if_called)

    text = call_details_text("x" * (server.MAX_ISBN_LENGTH + 1))

    assert text == "Error: isbn must be 32 characters or fewer."


def test_get_book_details_reports_no_match(monkeypatch) -> None:
    monkeypatch.setattr(server, "open_library_details", lambda isbn: None)

    assert (
        call_details_text("9780000000000")
        == 'No book found with ISBN "9780000000000".'
    )


def test_get_book_details_hides_catalogue_failures_from_the_client(monkeypatch) -> None:
    def unavailable(isbn: str):
        raise LookupUnavailable("internal network details")

    monkeypatch.setattr(server, "open_library_details", unavailable)

    text = call_details_text("9780261103344")

    assert text == (
        "Open Library is temporarily unavailable. "
        "Please try this book search again later."
    )
    assert "internal network details" not in text


def test_get_book_details_logs_the_exception_but_not_the_isbn(
    monkeypatch, caplog
) -> None:
    """An unexpected bug is logged for diagnostics without echoing the ISBN."""

    def explode(isbn: str):
        raise RuntimeError("internal mapping bug")

    monkeypatch.setattr(server, "open_library_details", explode)
    caplog.set_level(logging.ERROR, logger="mcp_server.server")

    result = call_get_book_details("9780261103344")

    assert result.structured_content["status"] == "unavailable"
    assert "internal mapping bug" in caplog.text
    assert "9780261103344" not in caplog.text


def call_search_by_subject(subject: str):
    """Call the subject tool and return its complete protocol result."""

    async def call():
        async with Client(server.mcp) as client:
            return await client.call_tool(
                "search_by_subject",
                {"subject": subject},
                raise_on_error=False,
            )

    return asyncio.run(call())


def call_find_similar_books(isbn: str):
    """Call the similar-books tool and return its complete protocol result."""

    async def call():
        async with Client(server.mcp) as client:
            return await client.call_tool(
                "find_similar_books",
                {"isbn": isbn},
                raise_on_error=False,
            )

    return asyncio.run(call())


def test_search_by_subject_returns_readable_normalized_results(monkeypatch) -> None:
    results = [
        BookDetails(title="Dune", author="Frank Herbert", isbn="9780441013593", year=1965),
        BookDetails(title="Neuromancer", author="William Gibson", isbn="9780441569595"),
    ]
    monkeypatch.setattr(
        server,
        "search_open_library_subject",
        lambda subject, **paging: SearchPage(results=results, total=len(results)),
    )

    result = call_search_by_subject("  science fiction  ")
    text = result.content[0].text

    assert text.startswith('Found 2 books filed under "science fiction":')
    assert "1. Dune" in text
    assert "ISBN: 9780441013593" in text
    assert result.structured_content["status"] == "ok"
    assert result.structured_content["books"][0]["title"] == "Dune"


def test_search_by_subject_rejects_a_blank_subject_without_a_lookup(monkeypatch) -> None:
    def fail_if_called(subject: str, **paging):
        raise AssertionError("blank input must not call Open Library")

    monkeypatch.setattr(server, "search_open_library_subject", fail_if_called)

    assert (
        call_search_by_subject("   ").content[0].text
        == "Error: subject must not be blank."
    )


def test_find_similar_books_returns_readable_normalized_results(monkeypatch) -> None:
    results = [
        BookDetails(title="Foundation", author="Isaac Asimov", isbn="9780553293357"),
    ]
    monkeypatch.setattr(
        server,
        "open_library_similar",
        lambda isbn, **paging: SearchPage(results=results, total=1),
    )

    result = call_find_similar_books("9780441013593")
    text = result.content[0].text

    assert text.startswith('Found 1 books similar to "9780441013593":')
    assert "1. Foundation" in text
    assert result.structured_content["status"] == "ok"
    assert result.structured_content["books"][0]["isbn"] == "9780553293357"


def test_find_similar_books_reports_no_match_for_a_subjectless_book(monkeypatch) -> None:
    """A book with no usable subject yields an empty page, not an error."""
    monkeypatch.setattr(
        server, "open_library_similar", lambda isbn, **paging: SearchPage([], 0)
    )

    assert (
        call_find_similar_books("9780000000000").content[0].text
        == 'No books found similar to "9780000000000".'
    )


def test_find_similar_books_hides_catalogue_failures_from_the_client(monkeypatch) -> None:
    def unavailable(isbn: str, **paging):
        raise LookupUnavailable("internal network details")

    monkeypatch.setattr(server, "open_library_similar", unavailable)

    text = call_find_similar_books("9780441013593").content[0].text

    assert "temporarily unavailable" in text
    assert "internal network details" not in text


def test_a_repeat_tool_call_is_served_from_the_cache(monkeypatch) -> None:
    """The catalogue is asked once for a repeated question, not once per call."""
    calls = {"count": 0}

    def counted(title: str, **paging):
        calls["count"] += 1
        return SearchPage(
            results=[BookDetails(title="The Hobbit", isbn="9780261103344")], total=1
        )

    monkeypatch.setattr(server, "search_open_library", counted)

    first = call_search_book("The Hobbit")
    second = call_search_book("  The Hobbit  ")  # same question after normalising

    assert calls["count"] == 1
    assert first == second


def test_each_search_tool_caches_separately(monkeypatch) -> None:
    """One string means different things to different tools, so keys must differ."""
    seen: list[str] = []

    def title_search(title: str, **paging):
        seen.append("title")
        return SearchPage(results=[BookDetails(title="About Orwell")], total=1)

    def author_search(author: str, **paging):
        seen.append("author")
        return SearchPage(results=[BookDetails(title="Nineteen Eighty-Four")], total=1)

    monkeypatch.setattr(server, "search_open_library", title_search)
    monkeypatch.setattr(server, "search_open_library_author", author_search)

    call_search_book("George Orwell")
    call_search_by_author("George Orwell")

    assert seen == ["title", "author"]


def test_an_outage_is_not_cached(monkeypatch) -> None:
    """A failed call must be retried next time, not pinned for the whole TTL."""
    calls = {"count": 0}

    def flaky(title: str, **paging):
        calls["count"] += 1
        if calls["count"] == 1:
            raise LookupUnavailable("timed out")
        return SearchPage(
            results=[BookDetails(title="The Hobbit", isbn="9780261103344")], total=1
        )

    monkeypatch.setattr(server, "search_open_library", flaky)

    assert "temporarily unavailable" in call_search_book("The Hobbit")
    recovered = call_search_book("The Hobbit")

    assert calls["count"] == 2
    assert "The Hobbit" in recovered


def test_a_missing_author_profile_is_not_cached(monkeypatch) -> None:
    """An empty profile is usually a timeout, so the next call asks again."""
    calls = {"count": 0}

    def flaky(name: str):
        calls["count"] += 1
        return None if calls["count"] == 1 else AuthorDetails(name="Ted Chiang")

    monkeypatch.setattr(server, "open_library_author_details", flaky)

    call_get_author_details("Ted Chiang")
    result = call_get_author_details("Ted Chiang")

    assert calls["count"] == 2
    assert result.structured_content["status"] == "ok"


def test_get_author_details_logs_the_exception_but_not_the_name(
    monkeypatch, caplog
) -> None:
    """An unexpected author-profile bug is logged without echoing the name."""

    def explode(name: str):
        raise RuntimeError("internal mapping bug")

    monkeypatch.setattr(server, "open_library_author_details", explode)
    caplog.set_level(logging.ERROR, logger="mcp_server.server")

    result = call_get_author_details("Ursula K. Le Guin")

    assert result.structured_content["status"] == "unavailable"
    assert "internal mapping bug" in caplog.text
    assert "Ursula K. Le Guin" not in caplog.text
