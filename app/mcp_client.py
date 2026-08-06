"""Application-side adapter for Shelf Life MCP tools.

The browser application consumes normalized ``BookDetails`` and ``SearchPage``
values, while MCP clients receive protocol results containing both readable text
and structured data. This module is the only place that translates between those
two shapes.

The local web application uses FastMCP's in-memory transport. It still exercises
the MCP tool registration, validation, serialization, and client protocol, but
avoids launching a new operating-system process for every book added.
"""

import asyncio
from typing import Any

from fastmcp import Client

from app.details import BookDetails, SearchPage
from mcp_server.server import mcp


DEFAULT_LIMIT = 5


class MCPUnavailable(RuntimeError):
    """The local MCP call failed or returned an unusable protocol result."""


async def _call_tool(tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
    async with Client(mcp) as client:
        result = await client.call_tool(tool, arguments, raise_on_error=False)

    structured = result.structured_content
    if not isinstance(structured, dict):
        raise MCPUnavailable(f"{tool} did not return structured content")
    return structured


def _details(tool: str, payload: object) -> BookDetails:
    if not isinstance(payload, dict):
        raise MCPUnavailable(f"{tool} returned an invalid book record")

    title = payload.get("title")
    if not isinstance(title, str) or not title.strip():
        raise MCPUnavailable(f"{tool} returned a book without a title")

    author = payload.get("author")
    isbn = payload.get("isbn")
    year = payload.get("year")
    cover_url = payload.get("cover_url")

    if author is not None and not isinstance(author, str):
        raise MCPUnavailable(f"{tool} returned an invalid author")
    if isbn is not None and not isinstance(isbn, str):
        raise MCPUnavailable(f"{tool} returned an invalid ISBN")
    if year is not None and (isinstance(year, bool) or not isinstance(year, int)):
        raise MCPUnavailable(f"{tool} returned an invalid year")
    if cover_url is not None and not isinstance(cover_url, str):
        raise MCPUnavailable(f"{tool} returned an invalid cover URL")

    return BookDetails(
        title=title.strip(),
        author=author,
        isbn=isbn,
        year=year,
        cover_url=cover_url,
    )


def _respond(tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Call one tool, turning any transport failure into ``MCPUnavailable``."""
    try:
        return asyncio.run(_call_tool(tool, arguments))
    except MCPUnavailable:
        raise
    except Exception as exc:
        raise MCPUnavailable(f"{tool} MCP call failed") from exc


def _total(response: dict[str, Any], fallback: int) -> int:
    reported = response.get("total")
    if isinstance(reported, bool) or not isinstance(reported, int) or reported < 0:
        return fallback
    return reported


def _page(tool: str, arguments: dict[str, Any]) -> SearchPage:
    """Call one search tool and return its normalized page of matches.

    Both searches answer with the same envelope, so the status handling is
    shared: ``no_match`` is an empty page, anything other than ``ok`` is a
    failure the caller should treat as the backend being unavailable.
    """
    response = _respond(tool, arguments)

    status = response.get("status")
    if status == "no_match":
        return SearchPage(results=[], total=_total(response, 0))
    if status != "ok":
        raise MCPUnavailable(f"{tool} MCP status was {status!r}")

    books = response.get("books")
    if not isinstance(books, list):
        raise MCPUnavailable(f"{tool} returned an invalid books list")

    results = [_details(tool, book) for book in books]
    return SearchPage(results=results, total=_total(response, len(results)))


def search_book(
    title: str, *, limit: int = DEFAULT_LIMIT, offset: int = 0
) -> SearchPage:
    """Call the local MCP title search and return one normalized page."""
    return _page(
        "search_book", {"title": title, "limit": limit, "offset": offset}
    )


def search_author(
    author: str, *, limit: int = DEFAULT_LIMIT, offset: int = 0
) -> SearchPage:
    """Call the local MCP author search and return one normalized page."""
    return _page(
        "search_by_author", {"author": author, "limit": limit, "offset": offset}
    )


def get_book_details(isbn: str) -> BookDetails | None:
    """Call the local MCP ISBN lookup, or return ``None`` if there is no such book."""
    tool = "get_book_details"
    response = _respond(tool, {"isbn": isbn})

    status = response.get("status")
    if status == "no_match":
        return None
    if status != "ok":
        raise MCPUnavailable(f"{tool} MCP status was {status!r}")

    return _details(tool, response.get("book"))
