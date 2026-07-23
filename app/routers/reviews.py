"""Review endpoints: rate and review a book."""

import sqlite3

from fastapi import APIRouter, Depends, status

from app.db import get_db
from app.models import Review, ReviewCreate
from app.routers.books import fetch_book


router = APIRouter(prefix="/books", tags=["reviews"])


@router.get("/{book_id}/reviews", response_model=list[Review])
def list_reviews(
    book_id: int,
    connection: sqlite3.Connection = Depends(get_db),
) -> list[dict]:
    """List the reviews on a book, newest first."""
    fetch_book(connection, book_id)
    rows = connection.execute(
        "SELECT * FROM reviews WHERE book_id = ? ORDER BY created_at DESC, id DESC",
        (book_id,),
    ).fetchall()
    return [dict(row) for row in rows]


@router.post(
    "/{book_id}/reviews", response_model=Review, status_code=status.HTTP_201_CREATED
)
def create_review(
    book_id: int,
    payload: ReviewCreate,
    connection: sqlite3.Connection = Depends(get_db),
) -> dict:
    """Add a rating (1-5) and optional review text to a book."""
    fetch_book(connection, book_id)
    cursor = connection.execute(
        "INSERT INTO reviews (book_id, rating, text) VALUES (?, ?, ?)",
        (book_id, payload.rating, payload.text),
    )
    connection.commit()

    row = connection.execute(
        "SELECT * FROM reviews WHERE id = ?", (cursor.lastrowid,)
    ).fetchone()
    return dict(row)
