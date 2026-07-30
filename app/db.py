"""SQLite schema and connection helpers for Shelf Life."""

import os
import sqlite3
from collections.abc import Iterator
from pathlib import Path

from app.details import normalise_isbn


BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = BASE_DIR / "shelf_life.db"

SHELVES = ("reading", "finished", "wishlist")

SCHEMA = """
CREATE TABLE IF NOT EXISTS books (
    id              INTEGER PRIMARY KEY,
    title           TEXT NOT NULL,
    author          TEXT,
    isbn            TEXT,
    cover_url       TEXT,
    year            INTEGER,
    shelf           TEXT NOT NULL DEFAULT 'reading'
                    CHECK (shelf IN ('reading', 'finished', 'wishlist')),
    details_pending INTEGER NOT NULL DEFAULT 0,
    identity_key    TEXT NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS reviews (
    id         INTEGER PRIMARY KEY,
    book_id    INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    rating     INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    text       TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_books_shelf ON books(shelf);
CREATE INDEX IF NOT EXISTS idx_reviews_book_id ON reviews(book_id);
"""


def _ensure_book_identity_column(connection: sqlite3.Connection) -> None:
    """Add the identity column when opening a database made by an older build."""
    columns = {
        row["name"] for row in connection.execute("PRAGMA table_info(books)").fetchall()
    }
    if "identity_key" not in columns:
        connection.execute("ALTER TABLE books ADD COLUMN identity_key TEXT")


def _migrate_unique_books(connection: sqlite3.Connection) -> None:
    """Merge duplicate ISBNs and enforce one tracked record per ISBN.

    The oldest book is the survivor, so its current shelf remains unchanged.
    Metadata missing from that record is filled from a duplicate when possible.
    If reviews exist across duplicate rows, the newest review is retained and
    attached to the survivor. Legacy rows with no ISBN are preserved under an
    internal per-row key; new builds no longer create such rows.
    """
    _ensure_book_identity_column(connection)
    connection.execute("DROP INDEX IF EXISTS uq_books_identity")
    rows = connection.execute("SELECT * FROM books ORDER BY id").fetchall()
    groups: dict[str, list[sqlite3.Row]] = {}
    for row in rows:
        isbn = normalise_isbn(row["isbn"])
        key = f"isbn:{isbn}" if isbn else f"legacy:{row['id']}"
        groups.setdefault(key, []).append(row)

    for key, duplicates in groups.items():
        keeper = duplicates[0]
        duplicate_ids = [row["id"] for row in duplicates]
        placeholders = ", ".join("?" for _ in duplicate_ids)

        latest_review = connection.execute(
            f"""
            SELECT *
            FROM reviews
            WHERE book_id IN ({placeholders})
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """,
            duplicate_ids,
        ).fetchone()
        connection.execute(
            f"DELETE FROM reviews WHERE book_id IN ({placeholders})", duplicate_ids
        )

        def first_value(field: str):
            return next(
                (row[field] for row in duplicates if row[field] not in (None, "")),
                None,
            )

        connection.execute(
            """
            UPDATE books
            SET author = ?,
                isbn = ?,
                cover_url = ?,
                year = ?,
                details_pending = ?,
                identity_key = ?
            WHERE id = ?
            """,
            (
                first_value("author"),
                first_value("isbn"),
                first_value("cover_url"),
                first_value("year"),
                0 if any(not row["details_pending"] for row in duplicates) else 1,
                key,
                keeper["id"],
            ),
        )

        if latest_review is not None:
            connection.execute(
                """
                INSERT INTO reviews (id, book_id, rating, text, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    latest_review["id"],
                    keeper["id"],
                    latest_review["rating"],
                    latest_review["text"],
                    latest_review["created_at"],
                ),
            )

        for duplicate in duplicates[1:]:
            connection.execute("DELETE FROM books WHERE id = ?", (duplicate["id"],))

    connection.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_books_identity
        ON books(identity_key)
        """
    )


def _migrate_single_user_reviews(connection: sqlite3.Connection) -> None:
    """Keep the newest review for each book and enforce one personal review.

    Earlier M1 builds allowed multiple reviews even though Shelf Life currently
    has one user. Existing local databases may therefore already contain
    duplicates. Keep the newest record before adding the unique index so those
    databases continue to start successfully.
    """
    connection.execute(
        """
        DELETE FROM reviews
        WHERE id NOT IN (
            SELECT MAX(id)
            FROM reviews
            GROUP BY book_id
        )
        """
    )
    connection.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_reviews_personal_book
        ON reviews(book_id)
        """
    )


def get_db_path() -> Path:
    """Return the active database file.

    Read from the environment on every call so tests can point at a temporary
    file without reloading the application module.
    """
    return Path(os.environ.get("SHELF_LIFE_DB", DEFAULT_DB_PATH))


def get_connection() -> sqlite3.Connection:
    """Open a connection with row access by name and cascading deletes on.

    ``check_same_thread`` is off because FastAPI may run the ``get_db``
    dependency and the endpoint that uses it on different threadpool workers.
    Each request still gets its own connection, so no two threads ever touch
    one connection at the same time.
    """
    connection = sqlite3.connect(get_db_path(), check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db() -> None:
    """Create the schema if it does not exist yet."""
    get_db_path().parent.mkdir(parents=True, exist_ok=True)
    connection = get_connection()
    try:
        connection.executescript(SCHEMA)
        _migrate_unique_books(connection)
        _migrate_single_user_reviews(connection)
        connection.commit()
    finally:
        connection.close()


def get_db() -> Iterator[sqlite3.Connection]:
    """FastAPI dependency yielding a per-request connection."""
    connection = get_connection()
    try:
        yield connection
    finally:
        connection.close()
