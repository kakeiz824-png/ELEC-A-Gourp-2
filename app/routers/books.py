"""Book endpoints: search by title or author, add, list by shelf, move, delete."""

import logging
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.db import get_db
from app.details import normalise_isbn
from app.lookup import BookDetails, lookup
from app.models import (
    Book,
    BookCandidate,
    BookCreate,
    BookWithReviews,
    Review,
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
    book["details_pending"] = bool(book["details_pending"])
    return book


def fetch_book(connection: sqlite3.Connection, book_id: int) -> sqlite3.Row:
    """Return a book row or raise 404."""
    row = connection.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()
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


def candidate_payload(candidate: search.Candidate) -> dict:
    """Flatten one candidate into the shape ``BookCandidate`` describes."""
    return {
        "title": candidate.details.title,
        "author": candidate.details.author,
        "isbn": candidate.details.isbn,
        "cover_url": candidate.details.cover_url,
        "year": candidate.details.year,
        "matched": candidate.matched,
    }


def selected_details(payload: BookCreate) -> BookDetails | None:
    """Re-run the user's search and return the candidate they picked.

    The search is repeated rather than trusting the submitted metadata, so a
    client cannot invent a title, author, or cover for an ISBN.  It has to be the
    same search: a book found by author is not necessarily found by its own
    title, so ``query`` decides which search runs.
    """
    selected_isbn = normalise_isbn(payload.isbn)
    pool = (
        search.by_query(payload.query)
        if payload.query
        else search.by_title(payload.title)
    )
    return next(
        (
            candidate.details
            for candidate in pool
            if normalise_isbn(candidate.details.isbn) == selected_isbn
        ),
        None,
    )


@router.get("", response_model=list[Book])
def list_books(
    shelf: Shelf | None = Query(default=None, description="Filter by shelf"),
    connection: sqlite3.Connection = Depends(get_db),
) -> list[dict]:
    """List books, newest first, optionally filtered to one shelf."""
    if shelf is None:
        rows = connection.execute(
            "SELECT * FROM books ORDER BY created_at DESC, id DESC"
        ).fetchall()
    else:
        rows = connection.execute(
            "SELECT * FROM books WHERE shelf = ? ORDER BY created_at DESC, id DESC",
            (shelf,),
        ).fetchall()
    return [row_to_book(row) for row in rows]


@router.get("/search", response_model=list[BookCandidate])
def search_books(
    q: str | None = Query(
        default=None,
        min_length=1,
        max_length=300,
        description="A title or an author's name; both searches run and merge",
    ),
    title: str | None = Query(
        default=None, min_length=1, max_length=300, description="Search titles only"
    ),
    author: str | None = Query(
        default=None, min_length=1, max_length=300, description="Search authors only"
    ),
) -> list[dict]:
    """Search for selectable ISBN-bearing candidates without storing anything.

    ``q`` is what the browser sends, because its one search box cannot say which
    kind of thing was typed.  ``title`` and ``author`` stay available for clients
    that do know, and for asking one catalogue index in isolation.
    """
    if q is not None:
        candidates = search.by_query(q)
    elif title is not None:
        candidates = search.by_title(title)
    elif author is not None:
        candidates = search.by_author(author)
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Provide q, title, or author.",
        )
    return [candidate_payload(candidate) for candidate in candidates]


@router.get("/recent", response_model=list[Book])
def recent_books(
    limit: int = Query(default=5, ge=1, le=50, description="How many to return"),
    connection: sqlite3.Connection = Depends(get_db),
) -> list[dict]:
    """List the most recently added books, newest first.

    Declared before ``/{book_id}`` so the literal path ``/books/recent`` is not
    captured as a book id.
    """
    rows = connection.execute(
        "SELECT * FROM books ORDER BY created_at DESC, id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [row_to_book(row) for row in rows]


@router.post("", response_model=Book, status_code=status.HTTP_201_CREATED)
def create_book(
    payload: BookCreate,
    connection: sqlite3.Connection = Depends(get_db),
) -> dict:
    """Add the ISBN candidate selected by the user."""
    if payload.isbn:
        details = selected_details(payload)
    else:
        # Backward compatibility for API clients created before the search UI.
        details = safe_lookup(payload.title)
    if details is None or normalise_isbn(details.isbn) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "isbn_not_found",
                "message": "没有找到带 ISBN 的书籍，请检查书名或稍后重试。",
            },
        )
    result = save_book(
        connection,
        shelf=payload.shelf,
        details=details,
    )
    book = row_to_book(result.row)
    if not result.created:
        shelf_name = {
            "reading": "阅读中",
            "finished": "已读完",
            "wishlist": "愿望清单",
        }[book["shelf"]]
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "book_exists",
                "message": f"这本书已经存在于“{shelf_name}”书架。",
                "book": book,
            },
        )
    return book


@router.get("/{book_id}", response_model=BookWithReviews)
def get_book(
    book_id: int,
    connection: sqlite3.Connection = Depends(get_db),
) -> dict:
    """Get one book together with its reviews."""
    book = row_to_book(fetch_book(connection, book_id))
    rows = connection.execute(
        "SELECT * FROM reviews WHERE book_id = ? ORDER BY created_at DESC, id DESC",
        (book_id,),
    ).fetchall()
    book["reviews"] = [Review(**dict(row)) for row in rows]
    return book


@router.patch("/{book_id}/shelf", response_model=Book)
def move_book(
    book_id: int,
    payload: ShelfUpdate,
    connection: sqlite3.Connection = Depends(get_db),
) -> dict:
    """Move a book to another shelf."""
    fetch_book(connection, book_id)
    connection.execute(
        "UPDATE books SET shelf = ? WHERE id = ?", (payload.shelf, book_id)
    )
    connection.commit()
    return row_to_book(fetch_book(connection, book_id))


@router.post("/{book_id}/enrich", response_model=Book)
def enrich_book(
    book_id: int,
    connection: sqlite3.Connection = Depends(get_db),
) -> dict:
    """Retry the lookup for a book whose details are still pending."""
    row = fetch_book(connection, book_id)
    details = safe_lookup(row["title"])
    if details is None or normalise_isbn(details.isbn) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "isbn_not_found",
                "message": "没有找到带 ISBN 的书籍，请检查书名或稍后重试。",
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
            WHERE id = ?
            """,
            (
                details.title,
                details.author,
                normalized_isbn,
                details.cover_url,
                details.year,
                identity_key,
                book_id,
            ),
        )
        connection.commit()
    except sqlite3.IntegrityError:
        connection.rollback()
        existing = connection.execute(
            "SELECT * FROM books WHERE identity_key = ?", (identity_key,)
        ).fetchone()
        if existing is None:
            raise
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "book_exists",
                "message": "这本书已经存在于你的书库。",
                "book": row_to_book(existing),
            },
        )
    return row_to_book(fetch_book(connection, book_id))


@router.delete("/{book_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_book(
    book_id: int,
    connection: sqlite3.Connection = Depends(get_db),
) -> None:
    """Delete a book; its reviews go with it."""
    fetch_book(connection, book_id)
    connection.execute("DELETE FROM books WHERE id = ?", (book_id,))
    connection.commit()
