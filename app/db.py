"""SQLite schema and connection helpers for Shelf Life."""

import os
import sqlite3
from collections.abc import Iterator
from pathlib import Path


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
