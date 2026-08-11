"""Shelf Life MCP tools.

Run this module from the repository root with::

    python -m mcp_server.server

FastMCP uses the STDIO transport by default, which lets MCP Inspector and
desktop MCP clients launch the server as a local subprocess.

Three tools are exposed. The two searches page through the catalogue, because
the browser lists every match rather than the first handful, and an author like
J. K. Rowling has hundreds. ``get_book_details`` resolves one ISBN, which is how
an add is confirmed: the ISBN identifies the book, so nothing has to trust
metadata a client sent.
"""

import logging
from collections.abc import Callable

from fastmcp import FastMCP
from fastmcp.tools.tool import ToolResult

from app.details import AuthorDetails, BookDetails, SearchPage
from app.openlibrary import LookupUnavailable
from app.openlibrary import get_author_details as open_library_author_details
from app.openlibrary import get_book_details as open_library_details
from app.openlibrary import search_author as search_open_library_author
from app.openlibrary import search_book as search_open_library


logger = logging.getLogger(__name__)

MAX_TITLE_LENGTH = 300
MAX_AUTHOR_LENGTH = 300
MAX_ISBN_LENGTH = 32
MAX_RESULTS = 50
DEFAULT_RESULTS = 5

mcp = FastMCP(
    name="Shelf Life",
    instructions=(
        "Search the public Open Library catalogue for books. "
        "Use search_book when a user knows a full or partial book title, "
        "search_by_author when a user names a writer and wants the books that "
        "writer wrote, get_book_details to resolve one ISBN, and "
        "get_author_details to fetch a writer's biography and dates."
    ),
)


def _show(value: object | None) -> str:
    """Return readable text for optional catalogue values."""
    return str(value) if value not in (None, "") else "Unknown"


_BOOK_FIELDS: tuple[tuple[str, str], ...] = (
    ("title", "Title"),
    ("author", "Author"),
    ("year", "First published"),
    ("isbn", "ISBN"),
    ("cover_url", "Cover"),
)


def _format_book(position: int, book: BookDetails) -> str:
    """Format one normalized catalogue result for an AI client."""
    lines = [f"{position}. {book.title}"]
    lines.extend(
        f"   {label}: {_show(getattr(book, name))}"
        for name, label in _BOOK_FIELDS
        if name != "title"
    )
    return "\n".join(lines)


def _book_payload(book: BookDetails) -> dict[str, str | int | None]:
    """Return the stable data shape consumed by application-side MCP clients."""
    return {name: getattr(book, name) for name, _ in _BOOK_FIELDS}


_AUTHOR_FIELDS: tuple[tuple[str, str], ...] = (
    ("name", "Name"),
    ("birth_date", "Born"),
    ("death_date", "Died"),
    ("work_count", "Works"),
    ("bio", "Biography"),
    ("photo_url", "Photo"),
)


def _format_author(author: AuthorDetails) -> str:
    """Format one normalized author profile for an AI client."""
    lines = [author.name]
    lines.extend(
        f"   {label}: {_show(getattr(author, name))}"
        for name, label in _AUTHOR_FIELDS
        if name != "name"
    )
    return "\n".join(lines)


def _author_payload(author: AuthorDetails) -> dict[str, str | int | None]:
    """Return the stable author data shape consumed by MCP clients."""
    return {name: getattr(author, name) for name, _ in _AUTHOR_FIELDS}


def _invalid(message: str) -> ToolResult:
    """Reject a call without contacting the catalogue."""
    return ToolResult(
        content=f"Error: {message}",
        structured_content={"status": "invalid_input", "books": [], "total": 0},
        is_error=True,
    )


def _unavailable() -> ToolResult:
    """Report an outage without leaking the underlying error."""
    return ToolResult(
        content=(
            "Open Library is temporarily unavailable. "
            "Please try this book search again later."
        ),
        structured_content={"status": "unavailable", "books": [], "total": 0},
        is_error=True,
    )


def _normalise_query(raw: str) -> str:
    """Collapse whitespace runs and drop control characters, keeping punctuation.

    Newlines, tabs, repeated spaces, and non-breaking spaces all become one
    space, so "Harry\n\nPotter" and "Harry Potter" reach the catalogue as the
    same query. Punctuation like ":", "'", "&" and "." is left alone because
    titles legitimately contain it.
    """
    cleaned = "".join(
        char if char.isprintable() else " " if char.isspace() else ""
        for char in raw
    )
    return " ".join(cleaned.split())

def _search_result(
    raw: str,
    *,
    field: str,
    max_length: int,
    phrase: str,
    search: Callable[..., SearchPage],
    limit: int,
    offset: int,
) -> ToolResult:
    """Normalise and validate one query, run a catalogue search, and shape the MCP result.

    Both searches report the same four outcomes -- invalid input, catalogue
    unavailable, no match, and ok -- so the shapes live here and each tool keeps
    only the description its AI client actually reads. ``phrase`` is how the
    match is described in the readable text: books "matching" a title, but books
    "written by" an author.
    """
    query = _normalise_query(raw)
    if not query:
        return _invalid(f"{field} must not be blank.")
    if len(query) > max_length:
        return _invalid(f"{field} must be {max_length} characters or fewer.")
    if not 1 <= limit <= MAX_RESULTS:
        return _invalid(f"limit must be between 1 and {MAX_RESULTS}.")
    if offset < 0:
        return _invalid("offset must not be negative.")

    try:
        page = search(query, limit=limit, offset=offset)
    except LookupUnavailable:
        return _unavailable()
    except Exception:
        logger.exception("Unexpected failure in the %s search", field)
        return _unavailable()

    if not page.results:
        return ToolResult(
            content=f'No books found {phrase} "{query}".',
            structured_content={
                "status": "no_match",
                "books": [],
                "total": page.total,
            },
        )

    shown = len(page.results)
    headline = f'Found {page.total} books {phrase} "{query}"'
    if shown != page.total:
        headline += f", showing {shown} from offset {offset}"
    formatted = "\n\n".join(
        _format_book(offset + position, book)
        for position, book in enumerate(page.results, start=1)
    )
    return ToolResult(
        content=f"{headline}:\n\n{formatted}",
        structured_content={
            "status": "ok",
            "books": [_book_payload(book) for book in page.results],
            "total": page.total,
        },
    )


@mcp.tool
def search_book(
    title: str, limit: int = DEFAULT_RESULTS, offset: int = 0
) -> ToolResult:
    """Search Open Library by title.

    Use this tool when the user gives a full or partial book title and wants
    likely matches. It returns readable results with author, first publication
    year, ISBN, and cover information when available, plus how many matches
    exist in total. Raise `offset` by `limit` to read the next page.
    """
    return _search_result(
        title,
        field="title",
        max_length=MAX_TITLE_LENGTH,
        phrase="matching",
        search=search_open_library,
        limit=limit,
        offset=offset,
    )


@mcp.tool
def search_by_author(
    author: str, limit: int = DEFAULT_RESULTS, offset: int = 0
) -> ToolResult:
    """Search Open Library for the books an author wrote.

    Use this tool when the user names a writer rather than a book, for example
    "what did Ursula K. Le Guin write". Searching that name as a title instead
    returns biographies and study guides about the author, not their own work.
    Raise `offset` by `limit` to read the next page.
    """
    return _search_result(
        author,
        field="author",
        max_length=MAX_AUTHOR_LENGTH,
        phrase="written by",
        search=search_open_library_author,
        limit=limit,
        offset=offset,
    )


@mcp.tool
def get_book_details(isbn: str) -> ToolResult:
    """Look up the one book that carries an ISBN.

    Use this tool when the user gives an ISBN, or when they have chosen one
    search result and you need that exact edition's title, author, publication
    year, and cover. An ISBN identifies a book, so this is also how an addition
    is confirmed without trusting metadata that came from elsewhere.
    """
    key = isbn.strip()
    if not key:
        return _invalid("isbn must not be blank.")
    if len(key) > MAX_ISBN_LENGTH:
        return _invalid(f"isbn must be {MAX_ISBN_LENGTH} characters or fewer.")

    try:
        book = open_library_details(key)
    except LookupUnavailable:
        return _unavailable()
    except Exception:
        logger.exception("Unexpected failure resolving the requested ISBN")
        return _unavailable()

    if book is None:
        return ToolResult(
            content=f'No book found with ISBN "{key}".',
            structured_content={"status": "no_match", "book": None},
        )

    return ToolResult(
        content=f"Found ISBN {key}:\n\n{_format_book(1, book)}",
        structured_content={"status": "ok", "book": _book_payload(book)},
    )


@mcp.tool
def get_author_details(name: str) -> ToolResult:
    """Look up one author's biography and life dates.

    Use this tool when the user wants to know about a writer -- who they are and
    when they lived -- rather than a list of their books. The name is resolved to
    the best-matching author in the catalogue. Not every author has a biography,
    dates, or photo on record, so those fields may be absent.
    """
    query = _normalise_query(name)
    if not query:
        return ToolResult(
            content="Error: name must not be blank.",
            structured_content={"status": "invalid_input", "author": None},
            is_error=True,
        )
    if len(query) > MAX_AUTHOR_LENGTH:
        return ToolResult(
            content=f"Error: name must be {MAX_AUTHOR_LENGTH} characters or fewer.",
            structured_content={"status": "invalid_input", "author": None},
            is_error=True,
        )

    try:
        author = open_library_author_details(query)
    except LookupUnavailable:
        return ToolResult(
            content=(
                "Open Library is temporarily unavailable. "
                "Please try this author lookup again later."
            ),
            structured_content={"status": "unavailable", "author": None},
            is_error=True,
        )
    except Exception:
        logger.exception("Unexpected failure resolving the requested author")
        return ToolResult(
            content=(
                "Open Library is temporarily unavailable. "
                "Please try this author lookup again later."
            ),
            structured_content={"status": "unavailable", "author": None},
            is_error=True,
        )

    if author is None:
        return ToolResult(
            content=f'No author found matching "{query}".',
            structured_content={"status": "no_match", "author": None},
        )

    return ToolResult(
        content=f"Found author:\n\n{_format_author(author)}",
        structured_content={"status": "ok", "author": _author_payload(author)},
    )


def main() -> None:
    """Run the local STDIO MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
