"""Pydantic request and response models."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator


Shelf = Literal["reading", "finished", "wishlist"]


class BookCreate(BaseModel):
    """Add a searched book; ISBN identifies the candidate the user selected.

    Only the ISBN is needed to confirm the book, because an ISBN identifies it:
    the server asks the catalogue about that ISBN rather than trusting any
    metadata sent alongside. ``title`` is used only when no ISBN is given, the
    contract that existed before the search UI.
    """

    title: str = Field(min_length=1, max_length=300)
    isbn: str | None = Field(default=None, max_length=32)
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


class BookCandidate(BaseModel):
    """One search result the user can choose to add."""

    title: str
    author: str | None
    isbn: str
    cover_url: str | None
    year: int | None


class SearchResults(BaseModel):
    """One page of candidates, and where that page sits in the whole result set.

    ``total`` and therefore ``pages`` come from the catalogue's own count, which
    counts what it matched rather than what survived filtering, so a page can
    hold fewer than ``per_page`` items while later pages still exist.
    """

    items: list[BookCandidate]
    page: int
    per_page: int
    pages: int
    total: int


class AuthorProfile(BaseModel):
    """An author's biography panel, best-effort from the catalogue.

    ``found`` says whether a profile was located: when it is false every other
    field is null and the browser simply hides the panel, so a writer the
    catalogue has no record of is not an error.
    """

    name: str
    bio: str | None = None
    birth_date: str | None = None
    death_date: str | None = None
    work_count: int | None = None
    photo_url: str | None = None
    found: bool = False


class BookWithReviews(Book):
    reviews: list[Review] = []


class Stats(BaseModel):
    total: int
    by_shelf: dict[str, int]
    review_count: int
    average_rating: float | None
