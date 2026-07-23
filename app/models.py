"""Pydantic request and response models."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator


Shelf = Literal["reading", "finished", "wishlist"]


class BookCreate(BaseModel):
    """Add a book by title only; everything else is filled in by lookup."""

    title: str = Field(min_length=1, max_length=300)
    shelf: Shelf = "reading"

    @field_validator("title")
    @classmethod
    def strip_title(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("title must not be blank")
        return stripped


class ShelfUpdate(BaseModel):
    shelf: Shelf


class ReviewCreate(BaseModel):
    rating: int = Field(ge=1, le=5)
    text: str | None = Field(default=None, max_length=2000)


class Review(BaseModel):
    id: int
    book_id: int
    rating: int
    text: str | None
    created_at: str


class Book(BaseModel):
    id: int
    title: str
    author: str | None
    isbn: str | None
    cover_url: str | None
    year: int | None
    shelf: Shelf
    details_pending: bool
    created_at: str


class BookWithReviews(Book):
    reviews: list[Review] = []


class Stats(BaseModel):
    total: int
    by_shelf: dict[str, int]
    review_count: int
    average_rating: float | None
