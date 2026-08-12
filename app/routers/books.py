"""Book endpoints: search by title or author, add, list by shelf, move, delete."""

import logging
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth import get_current_user
from app.db import get_db
from app.details import normalise_isbn
from app.lookup import BookDetails, details_for_isbn, lookup, tag_suggestions
from app.models import (
    Book,
    BookCreate,
    BookTagsUpdate,
    BookWithReviews,
    Review,
    SearchResults,
    Shelf,
    ShelfUpdate,
)
from app.services import search
from app.services.books import save_book


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/books", tags=["books"])


def row_to_book(row: sqlite3.Row) -> dict:
    """Turn a ``books`` row into the shape the API returns."""
    book = dict(row)
    book.pop("identity_key", None)
    book.pop("user_id", None)
    book["details_pending"] = bool(book["details_pending"])
    return book


MAX_TAGS_PER_BOOK = 20
MAX_TAG_LENGTH = 50


def _tags_for_books(
    connection: sqlite3.Connection, book_ids: list[int]
) -> dict[int, list[str]]:
    """Map book ids to their tag names, sorted case-insensitively."""
    if not book_ids:
        return {}
    placeholders = ", ".join("?" for _ in book_ids)
    # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query -- placeholders is only "?, ?, ?"; values bound via parameters. See docs/security-triage.md.
    rows = connection.execute(
        f"""
        SELECT bt.book_id, t.name
        FROM book_tags bt
        JOIN tags t ON t.id = bt.tag_id
        WHERE bt.book_id IN ({placeholders})
        ORDER BY t.name COLLATE NOCASE
        """,
        book_ids,
    ).fetchall()
    mapping: dict[int, list[str]] = {book_id: [] for book_id in book_ids}
    for row in rows:
        mapping.setdefault(row["book_id"], []).append(row["name"])
    return mapping


def _normalise_tag_names(raw: list[str]) -> list[str]:
    """Strip, drop blanks, dedupe case-insensitively, and bound the tag set."""
    names: list[str] = []
    seen: set[str] = set()
    for value in raw:
        if not isinstance(value, str):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Tags must be strings.",
            )
        name = value.strip()
        if not name:
            continue
        if len(name) > MAX_TAG_LENGTH:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Tag is too long (max {MAX_TAG_LENGTH} characters).",
            )
        key = name.casefold()
        if key in seen:
            continue
        seen.add(key)
        names.append(name)
    if len(names) > MAX_TAGS_PER_BOOK:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Too many tags (max {MAX_TAGS_PER_BOOK}).",
        )
    return names


def _replace_book_tags(
    connection: sqlite3.Connection, book_id: int, names: list[str]
) -> None:
    """Set a book's tags to exactly ``names``, reusing tags and pruning orphans.

    Tag rows are shared across books and matched case-insensitively, so an
    existing tag is reused rather than duplicated, and a tag left on no book is
    deleted. The caller commits; this leaves the transaction open so an add can
    apply categories in the same unit of work that created the book.
    """
    connection.execute("DELETE FROM book_tags WHERE book_id = ?", (book_id,))
    for name in names:
        row = connection.execute(
            "SELECT id FROM tags WHERE name = ? COLLATE NOCASE", (name,)
        ).fetchone()
        if row is None:
            cursor = connection.execute("INSERT INTO tags (name) VALUES (?)", (name,))
            tag_id = cursor.lastrowid
        else:
            tag_id = row["id"]
        connection.execute(
            "INSERT INTO book_tags (book_id, tag_id) VALUES (?, ?)",
            (book_id, tag_id),
        )
    connection.execute(
        "DELETE FROM tags WHERE id NOT IN (SELECT DISTINCT tag_id FROM book_tags)"
    )


def _auto_categorize(
    connection: sqlite3.Connection, book_id: int, isbn: str | None
) -> None:
    """Best-effort: file a newly added book under its broad catalogue categories.

    The same category suggestions the tag editor offers are applied
    automatically, so a fresh library is browsable by category and has something
    for recommendations to work from without any manual tagging. A slow or
    offline catalogue simply leaves the book untagged; this never fails the add.
    Only called for a freshly created book, so it never overwrites tags a reader
    set by hand.
    """
    if not isbn:
        return
    try:
        categories = tag_suggestions(isbn)
        if categories:
            _replace_book_tags(connection, book_id, categories)
            connection.commit()
    except Exception:
        # Categorisation is a bonus on top of an already-saved book: a slow or
        # failed catalogue call, or a transient database lock while writing the
        # tags, must never turn a successful add into a 500. Roll back only the
        # partial tag writes -- the book row was committed by ``save_book``.
        logger.warning("Auto-categorisation failed for %r", isbn, exc_info=True)
        try:
            connection.rollback()
        except Exception:
            pass


def fetch_book(
    connection: sqlite3.Connection, book_id: int, user_id: int
) -> sqlite3.Row:
    """Return one of the user's books or raise 404.

    Scoping by ``user_id`` means another user's book id is indistinguishable from
    a missing one, so a caller can neither read nor act on books they do not own.
    """
    row = connection.execute(
        "SELECT * FROM books WHERE id = ? AND user_id = ?", (book_id, user_id)
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Book not found")
    return row


def safe_lookup(title: str) -> BookDetails | None:
    """Look a title up, treating backend failure as no usable result."""
    try:
        return lookup(title)
    except Exception:
        logger.warning("Lookup failed for %r", title, exc_info=True)
        return None


def candidate_payload(details: BookDetails) -> dict:
    """Flatten one candidate into the shape ``BookCandidate`` describes."""
    return {
        "title": details.title,
        "author": details.author,
        "isbn": details.isbn,
        "cover_url": details.cover_url,
        "year": details.year,
    }


def confirm_isbn(isbn: str) -> BookDetails | None:
    """Ask the catalogue about one ISBN, treating a failure as no such book.

    The catalogue is asked rather than the submitted metadata being trusted, so
    a client cannot invent a title, author, or cover for an ISBN. Confirming by
    ISBN rather than by re-running the search also survives paging: the chosen
    candidate may have come from page seven, and catalogue relevance order can
    shift between two requests.
    """
    try:
        return details_for_isbn(isbn)
    except Exception:
        logger.warning("ISBN lookup failed for %r", isbn, exc_info=True)
        return None


@router.get("", response_model=list[Book])
def list_books(
    shelf: Shelf | None = Query(default=None, description="Filter by shelf"),
    tag: str | None = Query(default=None, description="Filter by tag name"),
    user: dict = Depends(get_current_user),
    connection: sqlite3.Connection = Depends(get_db),
) -> list[dict]:
    """List the user's books, newest first, optionally filtered to one shelf or tag."""
    if shelf is None and tag is None:
        rows = connection.execute(
            "SELECT * FROM books WHERE user_id = ? ORDER BY created_at DESC, id DESC",
            (user["id"],),
        ).fetchall()
    elif tag is None:
        rows = connection.execute(
            """
            SELECT * FROM books
            WHERE user_id = ? AND shelf = ?
            ORDER BY created_at DESC, id DESC
            """,
            (user["id"], shelf),
        ).fetchall()
    elif shelf is None:
        rows = connection.execute(
            """
            SELECT b.*
            FROM books b
            JOIN book_tags bt ON bt.book_id = b.id
            JOIN tags t ON t.id = bt.tag_id
            WHERE b.user_id = ? AND t.name = ? COLLATE NOCASE
            ORDER BY b.created_at DESC, b.id DESC
            """,
            (user["id"], tag),
        ).fetchall()
    else:
        rows = connection.execute(
            """
            SELECT b.*
            FROM books b
            JOIN book_tags bt ON bt.book_id = b.id
            JOIN tags t ON t.id = bt.tag_id
            WHERE b.user_id = ? AND t.name = ? COLLATE NOCASE AND b.shelf = ?
            ORDER BY b.created_at DESC, b.id DESC
            """,
            (user["id"], tag, shelf),
        ).fetchall()

    tags = _tags_for_books(connection, [row["id"] for row in rows])
    books = [row_to_book(row) for row in rows]
    for book in books:
        book["tags"] = tags.get(book["id"], [])
    return books


@router.get("/search", response_model=SearchResults)
def search_books(
    title: str | None = Query(
        default=None, min_length=1, max_length=300, description="Search book titles"
    ),
    author: str | None = Query(
        default=None, min_length=1, max_length=300, description="Search book authors"
    ),
    page: int = Query(default=1, ge=1, description="1-based page number"),
    per_page: int = Query(
        default=search.DEFAULT_PER_PAGE,
        ge=1,
        le=search.MAX_PER_PAGE,
        description="Candidates per page",
    ),
    user: dict = Depends(get_current_user),
) -> dict:
    """Return one page of selectable candidates without storing anything.

    Exactly one of ``title`` and ``author`` is required. The browser sends
    whichever its Title/Author selector is set to, so the server never has to
    guess whether a string like "Dune" or "Harry Potter" names a book or a person
    -- for both of those, either reading is a real book by a real author.
    """
    if (title is None) == (author is None):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Provide exactly one of title or author.",
        )

    found = (
        search.by_title(title, page=page, per_page=per_page)
        if title is not None
        else search.by_author(author, page=page, per_page=per_page)
    )
    return {
        "items": [candidate_payload(details) for details in found.candidates],
        "page": found.page,
        "per_page": found.per_page,
        "pages": found.pages,
        "total": found.total,
    }


@router.get("/recent", response_model=list[Book])
def recent_books(
    limit: int = Query(default=5, ge=1, le=50, description="How many to return"),
    user: dict = Depends(get_current_user),
    connection: sqlite3.Connection = Depends(get_db),
) -> list[dict]:
    """List the user's most recently added books, newest first.

    Declared before ``/{book_id}`` so the literal path ``/books/recent`` is not
    captured as a book id.
    """
    rows = connection.execute(
        "SELECT * FROM books WHERE user_id = ? ORDER BY created_at DESC, id DESC LIMIT ?",
        (user["id"], limit),
    ).fetchall()
    return [row_to_book(row) for row in rows]


@router.post("", response_model=Book, status_code=status.HTTP_201_CREATED)
def create_book(
    payload: BookCreate,
    user: dict = Depends(get_current_user),
    connection: sqlite3.Connection = Depends(get_db),
) -> dict:
    """Add the ISBN candidate the user selected to their library."""
    if payload.isbn:
        details = confirm_isbn(payload.isbn)
    else:
        # Backward compatibility for API clients created before the search UI.
        details = safe_lookup(payload.title)
    if details is None or normalise_isbn(details.isbn) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "isbn_not_found",
                "message": "No book with an ISBN was found. Check the title or try again later.",
            },
        )
    result = save_book(
        connection,
        user_id=user["id"],
        shelf=payload.shelf,
        details=details,
    )
    book = row_to_book(result.row)
    if not result.created:
        shelf_name = {
            "reading": "Reading",
            "finished": "Finished",
            "wishlist": "Wishlist",
        }[book["shelf"]]
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "book_exists",
                "message": f"This book is already on your {shelf_name} shelf.",
                "book": book,
            },
        )
    _auto_categorize(connection, book["id"], details.isbn)
    try:
        book["tags"] = _tags_for_books(connection, [book["id"]]).get(book["id"], [])
    except Exception:
        # The book is saved; a failed tag read must not fail the add.
        logger.warning("Reading tags failed for book %s", book["id"], exc_info=True)
        book["tags"] = []
    return book


@router.put("/{book_id}/tags", response_model=Book)
def update_book_tags(
    book_id: int,
    payload: BookTagsUpdate,
    user: dict = Depends(get_current_user),
    connection: sqlite3.Connection = Depends(get_db),
) -> dict:
    """Replace one of the user's book's tags with the supplied set, cleaning up orphans."""
    fetch_book(connection, book_id, user["id"])
    names = _normalise_tag_names(payload.tags)

    _replace_book_tags(connection, book_id, names)
    connection.commit()

    book = row_to_book(fetch_book(connection, book_id, user["id"]))
    book["tags"] = _tags_for_books(connection, [book_id]).get(book_id, [])
    return book


@router.get("/{book_id}/tag-suggestions")
def book_tag_suggestions(
    book_id: int,
    user: dict = Depends(get_current_user),
    connection: sqlite3.Connection = Depends(get_db),
) -> dict[str, list[str]]:
    """Broad category suggestions from the catalogue for the tag editor."""
    row = fetch_book(connection, book_id, user["id"])
    if not row["isbn"]:
        return {"categories": []}
    return {"categories": tag_suggestions(row["isbn"])}


@router.get("/{book_id}", response_model=BookWithReviews)
def get_book(
    book_id: int,
    user: dict = Depends(get_current_user),
    connection: sqlite3.Connection = Depends(get_db),
) -> dict:
    """Get one of the user's books together with its reviews."""
    book = row_to_book(fetch_book(connection, book_id, user["id"]))
    rows = connection.execute(
        "SELECT * FROM reviews WHERE book_id = ? ORDER BY created_at DESC, id DESC",
        (book_id,),
    ).fetchall()
    book["reviews"] = [Review(**dict(row)) for row in rows]
    book["tags"] = _tags_for_books(connection, [book_id]).get(book_id, [])
    return book


@router.patch("/{book_id}/shelf", response_model=Book)
def move_book(
    book_id: int,
    payload: ShelfUpdate,
    user: dict = Depends(get_current_user),
    connection: sqlite3.Connection = Depends(get_db),
) -> dict:
    """Move one of the user's books to another shelf."""
    fetch_book(connection, book_id, user["id"])
    connection.execute(
        "UPDATE books SET shelf = ? WHERE id = ? AND user_id = ?",
        (payload.shelf, book_id, user["id"]),
    )
    connection.commit()
    return row_to_book(fetch_book(connection, book_id, user["id"]))


@router.post("/{book_id}/enrich", response_model=Book)
def enrich_book(
    book_id: int,
    user: dict = Depends(get_current_user),
    connection: sqlite3.Connection = Depends(get_db),
) -> dict:
    """Retry the lookup for one of the user's books whose details are pending."""
    row = fetch_book(connection, book_id, user["id"])
    details = safe_lookup(row["title"])
    if details is None or normalise_isbn(details.isbn) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "isbn_not_found",
                "message": "No book with an ISBN was found. Check the title or try again later.",
            },
        )

    normalized_isbn = normalise_isbn(details.isbn)
    identity_key = f"isbn:{normalized_isbn}"
    try:
        connection.execute(
            """
            UPDATE books
            SET title = ?, author = ?, isbn = ?, cover_url = ?, year = ?,
                details_pending = 0, identity_key = ?
            WHERE id = ? AND user_id = ?
            """,
            (
                details.title,
                details.author,
                normalized_isbn,
                details.cover_url,
                details.year,
                identity_key,
                book_id,
                user["id"],
            ),
        )
        connection.commit()
    except sqlite3.IntegrityError:
        connection.rollback()
        existing = connection.execute(
            "SELECT * FROM books WHERE user_id = ? AND identity_key = ?",
            (user["id"], identity_key),
        ).fetchone()
        if existing is None:
            raise
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "book_exists",
                "message": "This book is already in your library.",
                "book": row_to_book(existing),
            },
        )
    return row_to_book(fetch_book(connection, book_id, user["id"]))


@router.delete("/{book_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_book(
    book_id: int,
    user: dict = Depends(get_current_user),
    connection: sqlite3.Connection = Depends(get_db),
) -> None:
    """Delete one of the user's books; its reviews and orphaned tags go with it."""
    fetch_book(connection, book_id, user["id"])
    connection.execute(
        "DELETE FROM books WHERE id = ? AND user_id = ?", (book_id, user["id"])
    )
    connection.execute(
        "DELETE FROM tags WHERE id NOT IN (SELECT DISTINCT tag_id FROM book_tags)"
    )
    connection.commit()
