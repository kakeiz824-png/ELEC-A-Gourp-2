"""Book business rules shared by HTTP routes and future MCP tools."""

import sqlite3
from dataclasses import dataclass

from app.details import BookDetails, normalise_isbn


@dataclass(frozen=True)
class BookWriteResult:
    """The stored book and whether this request created it."""

    row: sqlite3.Row
    created: bool


def save_book(
    connection: sqlite3.Connection,
    *,
    user_id: int,
    shelf: str,
    details: BookDetails,
) -> BookWriteResult:
    """Create one tracked book for the user, or return their existing ISBN match.

    The database unique index on ``(user_id, identity_key)`` is the final guard,
    so simultaneous requests from separate browser tabs cannot create duplicate
    rows, and two users can each track the same ISBN independently.
    """
    normalized_isbn = normalise_isbn(details.isbn)
    if normalized_isbn is None:
        raise ValueError("A book must have an ISBN before it can be stored")
    identity_key = f"isbn:{normalized_isbn}"
    values = (
        user_id,
        details.title,
        details.author,
        normalized_isbn,
        details.cover_url,
        details.year,
        shelf,
        0,
        identity_key,
    )

    try:
        cursor = connection.execute(
            """
            INSERT INTO books (
                user_id, title, author, isbn, cover_url, year, shelf,
                details_pending, identity_key
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            values,
        )
        connection.commit()
        row = connection.execute(
            "SELECT * FROM books WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
        if row is None:
            raise RuntimeError("Book insert did not produce a stored book")
        return BookWriteResult(row=row, created=True)
    except sqlite3.IntegrityError:
        connection.rollback()
        row = connection.execute(
            "SELECT * FROM books WHERE user_id = ? AND identity_key = ?",
            (user_id, identity_key),
        ).fetchone()
        if row is None:
            raise
        return BookWriteResult(row=row, created=False)
