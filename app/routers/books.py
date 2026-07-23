"""Book endpoints: add by title, list by shelf, move shelf, delete."""

import logging
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.db import get_db
from app.lookup import BookDetails, lookup
from app.models import Book, BookCreate, BookWithReviews, Review, Shelf, ShelfUpdate


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/books", tags=["books"])


def row_to_book(row: sqlite3.Row) -> dict:
    """Turn a ``books`` row into the shape the API returns."""
    book = dict(row)
    book["details_pending"] = bool(book["details_pending"])
    return book


def fetch_book(connection: sqlite3.Connection, book_id: int) -> sqlite3.Row:
    """Return a book row or raise 404."""
    row = connection.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Book not found")
    return row


def safe_lookup(title: str) -> BookDetails | None:
    """Look a title up, treating any lookup failure as "no details yet".

    An outage in the lookup backend must never turn into a failed add: the book
    is saved with the typed title and picked up later by the enrich path.
    """
    try:
        return lookup(title)
    except Exception:
        logger.warning("Lookup failed for %r; saving title only", title, exc_info=True)
        return None


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


@router.post("", response_model=Book, status_code=status.HTTP_201_CREATED)
def create_book(
    payload: BookCreate,
    connection: sqlite3.Connection = Depends(get_db),
) -> dict:
    """Add a book from its title alone, auto-filling the rest via lookup."""
    details = safe_lookup(payload.title)

    cursor = connection.execute(
        """
        INSERT INTO books (title, author, isbn, cover_url, year, shelf, details_pending)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            details.title if details else payload.title,
            details.author if details else None,
            details.isbn if details else None,
            details.cover_url if details else None,
            details.year if details else None,
            payload.shelf,
            0 if details else 1,
        ),
    )
    connection.commit()

    return row_to_book(fetch_book(connection, cursor.lastrowid))


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
    if details is None:
        return row_to_book(row)

    connection.execute(
        """
        UPDATE books
        SET title = ?, author = ?, isbn = ?, cover_url = ?, year = ?, details_pending = 0
        WHERE id = ?
        """,
        (
            details.title,
            details.author,
            details.isbn,
            details.cover_url,
            details.year,
            book_id,
        ),
    )
    connection.commit()
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
