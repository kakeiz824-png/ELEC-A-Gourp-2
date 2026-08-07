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

from app.details import BookDetails, SearchPage
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


def test_server_registers_both_searches_with_ai_facing_descriptions() -> None:
    async def list_tools():
        async with Client(server.mcp) as client:
            return await client.list_tools()

    tools = asyncio.run(list_tools())
    described = {tool.name: tool.description for tool in tools}

    assert sorted(described) == [
        "get_book_details",
        "search_book",
        "search_by_author",
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
        "get_book_details",
        "search_book",
        "search_by_author",
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
