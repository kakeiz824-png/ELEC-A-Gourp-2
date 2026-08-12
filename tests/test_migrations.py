"""Migration checks for the move from a shared shelf to per-user libraries."""

import sqlite3

import pytest

from app.db import get_connection, init_db


# A books table as an early, pre-login build created it: no owner column and no
# identity_key. Opening such a database must upgrade it without crashing.
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


def _seed_legacy(database) -> None:
    connection = sqlite3.connect(database)
    try:
        connection.executescript(LEGACY_SCHEMA)
        connection.execute(
            """
            INSERT INTO books (title, author, isbn, year, shelf, details_pending)
            VALUES ('The Hobbit', 'J. R. R. Tolkien', '9780261103344', 1937, 'reading', 0)
            """
        )
        connection.execute(
            "INSERT INTO reviews (book_id, rating, text) VALUES (1, 5, 'Loved it')"
        )
        connection.commit()
    finally:
        connection.close()


def test_pre_login_shared_books_are_dropped(tmp_path, monkeypatch) -> None:
    """The old ownerless shared shelf is cleared so login starts each user empty."""
    database = tmp_path / "legacy.db"
    monkeypatch.setenv("SHELF_LIFE_DB", str(database))
    _seed_legacy(database)

    init_db()

    connection = get_connection()
    try:
        books = connection.execute("SELECT * FROM books").fetchall()
        reviews = connection.execute("SELECT * FROM reviews").fetchall()
        indexes = connection.execute("PRAGMA index_list(books)").fetchall()
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(books)")}
    finally:
        connection.close()

    # Ownerless legacy books (user_id IS NULL) and their reviews are removed.
    assert books == []
    assert reviews == []
    # The upgrade added the owner column and the composite identity guard.
    assert "user_id" in columns
    assert any(
        index["name"] == "uq_books_identity" and index["unique"] for index in indexes
    )


def test_two_users_can_hold_the_same_isbn(tmp_path, monkeypatch) -> None:
    """The unique index is now (user_id, identity_key), not identity_key alone."""
    database = tmp_path / "fresh.db"
    monkeypatch.setenv("SHELF_LIFE_DB", str(database))
    init_db()

    connection = get_connection()
    try:
        for user_id, sub in ((1, "sub-1"), (2, "sub-2")):
            connection.execute(
                "INSERT INTO users (id, google_sub, email) VALUES (?, ?, ?)",
                (user_id, sub, f"user{user_id}@example.com"),
            )
        # The same ISBN owned by two different users may coexist.
        for user_id in (1, 2):
            connection.execute(
                """
                INSERT INTO books
                    (user_id, title, isbn, shelf, details_pending, identity_key)
                VALUES (?, 'Dune', '9780441172719', 'reading', 0, 'isbn:9780441172719')
                """,
                (user_id,),
            )
        connection.commit()

        owners = [
            row["user_id"]
            for row in connection.execute("SELECT user_id FROM books ORDER BY user_id")
        ]
        assert owners == [1, 2]

        # A second copy for the SAME owner collides on (user_id, identity_key).
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO books
                    (user_id, title, isbn, shelf, details_pending, identity_key)
                VALUES (1, 'Dune again', '9780441172719', 'reading', 0, 'isbn:9780441172719')
                """
            )
    finally:
        connection.close()
