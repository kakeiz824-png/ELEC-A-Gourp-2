"""Review endpoints: rate and review a book."""

import sqlite3

from fastapi import APIRouter, Depends, Response, status

from app.db import get_db
from app.models import Review, ReviewCreate
from app.routers.books import fetch_book
from app.services.reviews import save_personal_review


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
    response: Response,
    connection: sqlite3.Connection = Depends(get_db),
) -> dict:
    """Create or update the user's rating and optional review text."""
    fetch_book(connection, book_id)
    result = save_personal_review(
        connection,
        book_id=book_id,
        rating=payload.rating,
        text=payload.text,
    )
    response.status_code = (
        status.HTTP_201_CREATED if result.created else status.HTTP_200_OK
    )
    return dict(result.row)
