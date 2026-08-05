"""Shelf Life MCP tools.

Run this module from the repository root with::

    python -m mcp_server.server

FastMCP uses the STDIO transport by default, which lets MCP Inspector and
desktop MCP clients launch the server as a local subprocess.
"""

from collections.abc import Callable

from fastmcp import FastMCP
from fastmcp.tools.tool import ToolResult

from app.details import BookDetails
from app.openlibrary import LookupUnavailable
from app.openlibrary import search_author as search_open_library_author
from app.openlibrary import search_book as search_open_library


MAX_TITLE_LENGTH = 300
MAX_AUTHOR_LENGTH = 300
MAX_RESULTS = 5

mcp = FastMCP(
    name="Shelf Life",
    instructions=(
        "Search the public Open Library catalogue for books. "
        "Use search_book when a user knows a full or partial book title, and "
        "search_by_author when a user names a writer and wants the books that "
        "writer wrote."
    ),
)


def _show(value: object | None) -> str:
    """Return readable text for optional catalogue values."""
    return str(value) if value not in (None, "") else "Unknown"


def _format_book(position: int, book: BookDetails) -> str:
    """Format one normalized catalogue result for an AI client."""
    return "\n".join(
        [
            f"{position}. {book.title}",
            f"   Author: {_show(book.author)}",
            f"   First published: {_show(book.year)}",
            f"   ISBN: {_show(book.isbn)}",
            f"   Cover: {_show(book.cover_url)}",
        ]
    )


def _book_payload(book: BookDetails) -> dict[str, str | int | None]:
    """Return the stable data shape consumed by application-side MCP clients."""
    return {
        "title": book.title,
        "author": book.author,
        "isbn": book.isbn,
        "year": book.year,
        "cover_url": book.cover_url,
    }


def _search_result(
    raw: str,
    *,
    field: str,
    limit: int,
    phrase: str,
    search: Callable[[str], list[BookDetails]],
) -> ToolResult:
    """Validate one query, run a catalogue search, and shape the MCP result.

    Both search tools report the same four outcomes -- invalid input, catalogue
    unavailable, no match, and ok -- so the shapes live here and each tool keeps
    only the description its AI client actually reads. ``phrase`` is how the
    match is described in the readable text: books "matching" a title, but books
    "written by" an author.
    """
    query = raw.strip()
    if not query:
        return ToolResult(
            content=f"Error: {field} must not be blank.",
            structured_content={"status": "invalid_input", "books": []},
            is_error=True,
        )
    if len(query) > limit:
        return ToolResult(
            content=f"Error: {field} must be {limit} characters or fewer.",
            structured_content={"status": "invalid_input", "books": []},
            is_error=True,
        )

    try:
        results = search(query)[:MAX_RESULTS]
    except LookupUnavailable:
        return ToolResult(
            content=(
                "Open Library is temporarily unavailable. "
                "Please try this book search again later."
            ),
            structured_content={"status": "unavailable", "books": []},
            is_error=True,
        )

    if not results:
        return ToolResult(
            content=f'No books found {phrase} "{query}".',
            structured_content={"status": "no_match", "books": []},
        )

    formatted = "\n\n".join(
        _format_book(position, book)
        for position, book in enumerate(results, start=1)
    )
    return ToolResult(
        content=f'Found {len(results)} books {phrase} "{query}":\n\n{formatted}',
        structured_content={
            "status": "ok",
            "books": [_book_payload(book) for book in results],
        },
    )


@mcp.tool
def search_book(title: str) -> ToolResult:
    """Search Open Library by title.

    Use this tool when the user gives a full or partial book title and wants
    likely matches. It returns up to five readable results with author, first
    publication year, ISBN, and cover information when available.
    """
    return _search_result(
        title,
        field="title",
        limit=MAX_TITLE_LENGTH,
        phrase="matching",
        search=search_open_library,
    )


@mcp.tool
def search_by_author(author: str) -> ToolResult:
    """Search Open Library for the books an author wrote.

    Use this tool when the user names a writer rather than a book, for example
    "what did Ursula K. Le Guin write". Searching that name as a title instead
    returns biographies and study guides about the author, not their own work.
    It returns up to five readable results with first publication year, ISBN,
    and cover information when available.
    """
    return _search_result(
        author,
        field="author",
        limit=MAX_AUTHOR_LENGTH,
        phrase="written by",
        search=search_open_library_author,
    )


def main() -> None:
    """Run the local STDIO MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
