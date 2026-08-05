"""Pydantic request and response models."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator


Shelf = Literal["reading", "finished", "wishlist"]


class BookCreate(BaseModel):
    """Add a searched book; ISBN identifies the candidate the user selected.

    ``query`` is what the user actually typed into the search box, which may have
    been an author's name.  It is sent back so the server can re-run the same
    search the candidate came from before trusting the ISBN; without it, a book
    found by author would be looked for by title and never confirmed.
    """

    title: str = Field(min_length=1, max_length=300)
    query: str | None = Field(default=None, max_length=300)
    isbn: str | None = Field(default=None, max_length=32)
    shelf: Shelf = "reading"

    @field_validator("title")
    @classmethod
    def strip_title(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("title must not be blank")
        return stripped

    @field_validator("query")
    @classmethod
    def strip_query(cls, value: str | None) -> str | None:
        """A blank query is no query, not a search for nothing."""
        if value is None:
            return None
        return value.strip() or None


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


class BookCandidate(BaseModel):
    """One search result the user can choose to add.

    ``matched`` says which search produced it, so a merged list can tell the user
    why a book is being offered: its title matched, or its author did.
    """

    title: str
    author: str | None
    isbn: str
    cover_url: str | None
    year: int | None
    matched: Literal["title", "author"]


class BookWithReviews(Book):
    reviews: list[Review] = []


class Stats(BaseModel):
    total: int
    by_shelf: dict[str, int]
    review_count: int
    average_rating: float | None
