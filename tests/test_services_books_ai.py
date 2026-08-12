"""Test suite for app.services.books.save_book.

LABEL: AI-generated (Studio 7, Part 1). Not yet evaluated or edited.
Target module: app/services/books.py -- the duplicate-safe book creation rule.

These tests were produced in one pass by asking the AI for a comprehensive
suite. Per the studio workflow they are committed UNEDITED so the raw
generate-and-run results can be recorded before the Part 2 evaluation.
"""

import sqlite3

import pytest

from app.db import get_connection, init_db
from app.details import BookDetails
from app.services.books import BookWriteResult, save_book


@pytest.fixture()
def connection(tmp_path, monkeypatch) -> sqlite3.Connection:
    """A fresh, fully migrated database (with the unique ISBN index) per test.

    A user row (id=1) is seeded so the books written here satisfy the owner
    foreign key; every ``save_book`` call below passes ``user_id=1``.
    """
    monkeypatch.setenv("SHELF_LIFE_DB", str(tmp_path / "shelf_life.db"))
    init_db()
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO users (id, google_sub, email, name, picture)
        VALUES (1, 'test-google-sub', 'tester@example.com', 'Tester', NULL)
        """
    )
    conn.commit()
    try:
        yield conn
    finally:
        conn.close()


def _details(**overrides) -> BookDetails:
    """A complete BookDetails with sensible defaults, overridable per field."""
    base = dict(
        title="The Pragmatic Programmer",
        author="Hunt & Thomas",
        isbn="978-0-13-595705-9",
        year=2019,
        cover_url="https://covers.example/pp.jpg",
    )
    base.update(overrides)
    return BookDetails(**base)


# --- Creating a new book -------------------------------------------------


def test_save_new_book_reports_created(connection):
    result = save_book(connection, user_id=1, shelf="reading", details=_details())
    assert result.created is True


def test_save_new_book_returns_write_result(connection):
    result = save_book(connection, user_id=1, shelf="reading", details=_details())
    assert isinstance(result, BookWriteResult)


def test_save_new_book_persists_title_and_author(connection):
    result = save_book(connection, user_id=1, shelf="reading", details=_details())
    assert result.row["title"] == "The Pragmatic Programmer"
    assert result.row["author"] == "Hunt & Thomas"


def test_save_new_book_stores_requested_shelf(connection):
    result = save_book(connection, user_id=1, shelf="wishlist", details=_details())
    assert result.row["shelf"] == "wishlist"


def test_save_new_book_stores_year_and_cover(connection):
    result = save_book(connection, user_id=1, shelf="reading", details=_details())
    assert result.row["year"] == 2019
    assert result.row["cover_url"] == "https://covers.example/pp.jpg"


def test_save_new_book_normalises_stored_isbn(connection):
    result = save_book(connection, user_id=1, shelf="reading", details=_details())
    # The hyphenated ISBN should be folded to digits before storage.
    assert result.row["isbn"] == "9780135957059"


def test_save_new_book_sets_identity_key_from_isbn(connection):
    result = save_book(connection, user_id=1, shelf="reading", details=_details())
    assert result.row["identity_key"] == "isbn:9780135957059"


def test_save_new_book_marks_details_not_pending(connection):
    result = save_book(connection, user_id=1, shelf="reading", details=_details())
    assert result.row["details_pending"] == 0


def test_save_new_book_inserts_exactly_one_row(connection):
    save_book(connection, user_id=1, shelf="reading", details=_details())
    count = connection.execute("SELECT COUNT(*) AS n FROM books").fetchone()["n"]
    assert count == 1


# --- Duplicate ISBN handling ---------------------------------------------


def test_duplicate_isbn_reports_not_created(connection):
    save_book(connection, user_id=1, shelf="reading", details=_details())
    second = save_book(connection, user_id=1, shelf="reading", details=_details())
    assert second.created is False


def test_duplicate_isbn_returns_the_original_row(connection):
    first = save_book(connection, user_id=1, shelf="reading", details=_details())
    second = save_book(connection, user_id=1, shelf="reading", details=_details())
    assert second.row["id"] == first.row["id"]


def test_duplicate_isbn_does_not_insert_a_second_row(connection):
    save_book(connection, user_id=1, shelf="reading", details=_details())
    save_book(connection, user_id=1, shelf="reading", details=_details())
    count = connection.execute("SELECT COUNT(*) AS n FROM books").fetchone()["n"]
    assert count == 1


def test_duplicate_add_does_not_move_existing_shelf(connection):
    save_book(connection, user_id=1, shelf="reading", details=_details())
    second = save_book(connection, user_id=1, shelf="finished", details=_details())
    # The existing book keeps its original shelf; the duplicate add is ignored.
    assert second.row["shelf"] == "reading"


def test_differently_formatted_isbn_is_the_same_book(connection):
    save_book(connection, user_id=1, shelf="reading", details=_details(isbn="978-0-13-595705-9"))
    second = save_book(
        connection, user_id=1, shelf="reading", details=_details(isbn="9780135957059")
    )
    assert second.created is False


def test_same_title_different_isbn_are_two_books(connection):
    save_book(connection, user_id=1, shelf="reading", details=_details(isbn="9780135957059"))
    second = save_book(
        connection, user_id=1, shelf="reading", details=_details(isbn="9781491950357")
    )
    assert second.created is True
    count = connection.execute("SELECT COUNT(*) AS n FROM books").fetchone()["n"]
    assert count == 2


# --- Missing / invalid ISBN ----------------------------------------------


def test_missing_isbn_raises_value_error(connection):
    with pytest.raises(ValueError):
        save_book(connection, user_id=1, shelf="reading", details=_details(isbn=None))


def test_isbn_of_only_punctuation_raises_value_error(connection):
    # Nothing digit-like survives normalisation, so there is no ISBN to store.
    with pytest.raises(ValueError):
        save_book(connection, user_id=1, shelf="reading", details=_details(isbn="---"))


def test_rejected_book_is_not_stored(connection):
    with pytest.raises(ValueError):
        save_book(connection, user_id=1, shelf="reading", details=_details(isbn=None))
    count = connection.execute("SELECT COUNT(*) AS n FROM books").fetchone()["n"]
    assert count == 0


# --- Optional metadata ----------------------------------------------------


def test_optional_fields_may_be_null(connection):
    result = save_book(
        connection,
        user_id=1,
        shelf="reading",
        details=_details(author=None, year=None, cover_url=None),
    )
    assert result.row["author"] is None
    assert result.row["year"] is None
    assert result.row["cover_url"] is None


def test_isbn_ten_with_check_character_is_preserved(connection):
    result = save_book(
        connection, user_id=1, shelf="reading", details=_details(isbn="0-306-40615-X")
    )
    assert result.row["isbn"] == "030640615X"
