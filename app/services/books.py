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
    shelf: str,
    details: BookDetails,
) -> BookWriteResult:
    """Create one tracked book or return the existing ISBN match.

    The database unique index is the final guard, so simultaneous requests from
    separate browser tabs cannot create duplicate rows.
    """
    normalized_isbn = normalise_isbn(details.isbn)
    if normalized_isbn is None:
        raise ValueError("A book must have an ISBN before it can be stored")
    identity_key = f"isbn:{normalized_isbn}"
    values = (
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
                title, author, isbn, cover_url, year, shelf,
                details_pending, identity_key
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
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
            "SELECT * FROM books WHERE identity_key = ?", (identity_key,)
        ).fetchone()
        if row is None:
            raise
        return BookWriteResult(row=row, created=False)
