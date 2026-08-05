"""Application-side adapter for Shelf Life MCP tools.

The browser application consumes normalized ``BookDetails`` values, while MCP
clients receive protocol results containing both readable text and structured
data. This module is the only place that translates between those two shapes.

The local web application uses FastMCP's in-memory transport. It still exercises
the MCP tool registration, validation, serialization, and client protocol, but
avoids launching a new operating-system process for every book added.
"""

import asyncio
from typing import Any

from fastmcp import Client

from app.details import BookDetails
from mcp_server.server import mcp


class MCPUnavailable(RuntimeError):
    """The local MCP call failed or returned an unusable protocol result."""


async def _call_tool(tool: str, arguments: dict[str, str]) -> dict[str, Any]:
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


def _books(tool: str, arguments: dict[str, str]) -> list[BookDetails]:
    """Call one search tool and return its normalized catalogue matches.

    Both search tools answer with the same envelope, so the status handling is
    shared: ``no_match`` is an empty result, anything other than ``ok`` is a
    failure the caller should treat as the backend being unavailable.
    """
    try:
        response = asyncio.run(_call_tool(tool, arguments))
    except MCPUnavailable:
        raise
    except Exception as exc:
        raise MCPUnavailable(f"{tool} MCP call failed") from exc

    status = response.get("status")
    if status == "no_match":
        return []
    if status != "ok":
        raise MCPUnavailable(f"{tool} MCP status was {status!r}")

    books = response.get("books")
    if not isinstance(books, list):
        raise MCPUnavailable(f"{tool} returned an invalid books list")
    return [_details(tool, book) for book in books]


def search_book(title: str) -> list[BookDetails]:
    """Call the local MCP title search and return normalized catalogue matches."""
    return _books("search_book", {"title": title})


def search_by_author(author: str) -> list[BookDetails]:
    """Call the local MCP author search and return normalized catalogue matches."""
    return _books("search_by_author", {"author": author})
