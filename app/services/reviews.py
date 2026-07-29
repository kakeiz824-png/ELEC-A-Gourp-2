"""Single-user review business rules shared by HTTP and future MCP tools."""

import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class ReviewWriteResult:
    """The stored review and whether this request created it."""

    row: sqlite3.Row
    created: bool


def save_personal_review(
    connection: sqlite3.Connection,
    *,
    book_id: int,
    rating: int,
    text: str | None,
) -> ReviewWriteResult:
    """Create or update the one personal review associated with a book."""
    existing = connection.execute(
        "SELECT id FROM reviews WHERE book_id = ?", (book_id,)
    ).fetchone()
    created = existing is None

    connection.execute(
        """
        INSERT INTO reviews (book_id, rating, text)
        VALUES (?, ?, ?)
        ON CONFLICT(book_id) DO UPDATE SET
            rating = excluded.rating,
            text = excluded.text
        """,
        (book_id, rating, text),
    )
    connection.commit()

    row = connection.execute(
        "SELECT * FROM reviews WHERE book_id = ?", (book_id,)
    ).fetchone()
    if row is None:  # Defensive: the upsert above must always produce a row.
        raise RuntimeError("Review upsert did not produce a stored review")
    return ReviewWriteResult(row=row, created=created)
