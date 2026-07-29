"""Compatibility checks for databases created by earlier Shelf Life builds."""

import sqlite3

from app.db import get_connection, init_db


LEGACY_SCHEMA = """
CREATE TABLE books (
    id              INTEGER PRIMARY KEY,
    title           TEXT NOT NULL,
    author          TEXT,
    isbn            TEXT,
    cover_url       TEXT,
    year            INTEGER,
    shelf           TEXT NOT NULL,
    details_pending INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE reviews (
    id         INTEGER PRIMARY KEY,
    book_id    INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    rating     INTEGER NOT NULL,
    text       TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def test_legacy_duplicates_are_merged_without_moving_the_original_book(
    tmp_path, monkeypatch
) -> None:
    database = tmp_path / "legacy.db"
    monkeypatch.setenv("SHELF_LIFE_DB", str(database))
    connection = sqlite3.connect(database)
    try:
        connection.executescript(LEGACY_SCHEMA)
        connection.execute(
            """
            INSERT INTO books
                (title, author, isbn, year, shelf, details_pending)
            VALUES
                ('The Hobbit', 'J. R. R. Tolkien', '9780261103344', 1937, 'reading', 0)
            """
        )
        connection.execute(
            """
            INSERT INTO books
                (title, isbn, shelf, details_pending)
            VALUES
                ('  the hobbit  ', '978-0-261-10334-4', 'wishlist', 1)
            """
        )
        connection.execute(
            "INSERT INTO reviews (book_id, rating, text) VALUES (1, 2, 'Older')"
        )
        connection.execute(
            "INSERT INTO reviews (book_id, rating, text) VALUES (2, 5, 'Newest')"
        )
        connection.commit()
    finally:
        connection.close()

    init_db()

    connection = get_connection()
    try:
        books = connection.execute("SELECT * FROM books").fetchall()
        reviews = connection.execute("SELECT * FROM reviews").fetchall()
        identity_indexes = connection.execute(
            "PRAGMA index_list(books)"
        ).fetchall()
    finally:
        connection.close()

    assert len(books) == 1
    assert books[0]["id"] == 1
    assert books[0]["shelf"] == "reading"
    assert books[0]["identity_key"] == "isbn:9780261103344"
    assert len(reviews) == 1
    assert reviews[0]["book_id"] == 1
    assert reviews[0]["rating"] == 5
    assert any(
        index["name"] == "uq_books_identity" and index["unique"]
        for index in identity_indexes
    )


def test_legacy_books_with_the_same_title_but_different_isbns_are_preserved(
    tmp_path, monkeypatch
) -> None:
    database = tmp_path / "same-title.db"
    monkeypatch.setenv("SHELF_LIFE_DB", str(database))
    connection = sqlite3.connect(database)
    try:
        connection.executescript(LEGACY_SCHEMA)
        connection.execute(
            """
            INSERT INTO books (title, author, isbn, shelf)
            VALUES ('Shared Title', 'Author One', '1111111111', 'reading')
            """
        )
        connection.execute(
            """
            INSERT INTO books (title, author, isbn, shelf)
            VALUES ('Shared Title', 'Author Two', '2222222222', 'wishlist')
            """
        )
        connection.commit()
    finally:
        connection.close()

    init_db()

    connection = get_connection()
    try:
        books = connection.execute(
            "SELECT isbn, identity_key FROM books ORDER BY id"
        ).fetchall()
    finally:
        connection.close()

    assert [book["isbn"] for book in books] == ["1111111111", "2222222222"]
    assert [book["identity_key"] for book in books] == [
        "isbn:1111111111",
        "isbn:2222222222",
    ]
