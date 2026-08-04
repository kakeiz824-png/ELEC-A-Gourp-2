"""SQLite schema and connection helpers for Shelf Life."""

import os
import sqlite3
from collections.abc import Iterator
from pathlib import Path

from app.details import normalise_isbn


BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = BASE_DIR / "shelf_life.db"

# In production we point at Turso (cloud libSQL) by setting TURSO_DATABASE_URL
# (a ``libsql://…`` URL) and TURSO_AUTH_TOKEN in the platform dashboard. When the
# URL is absent we fall back to a local SQLite file, so local dev and the test
# suite are unaffected.
TURSO_DATABASE_URL = os.environ.get("TURSO_DATABASE_URL", "").strip()
TURSO_AUTH_TOKEN = os.environ.get("TURSO_AUTH_TOKEN", "").strip()
USE_TURSO = bool(TURSO_DATABASE_URL)

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

        # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query -- placeholders is only "?, ?, ?"; values bound via parameters. See semgrep-triage.md.
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
        # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query -- placeholders is only "?, ?, ?"; values bound via parameters. See semgrep-triage.md.
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


# ---------------------------------------------------------------------------
# Turso / libSQL compatibility layer
#
# The ``libsql`` driver returns rows as plain tuples and raises ``ValueError``
# on constraint violations, whereas the rest of the app expects ``sqlite3``
# semantics: rows accessible by column name, ``dict(row)``, and
# ``sqlite3.IntegrityError``. These thin wrappers translate a libSQL connection
# into that shape so routers and services need no changes.
# ---------------------------------------------------------------------------


class _TursoRow:
    """A tuple row exposed with sqlite3.Row-style access (name, index, dict)."""

    __slots__ = ("_index", "_values")

    def __init__(self, columns: list[str], values: tuple) -> None:
        self._index = {name: position for position, name in enumerate(columns)}
        self._values = values

    def keys(self) -> list[str]:
        return list(self._index)

    def __getitem__(self, key):
        if isinstance(key, str):
            return self._values[self._index[key]]
        return self._values[key]

    def __contains__(self, key: str) -> bool:
        return key in self._index

    def __len__(self) -> int:
        return len(self._values)


class _TursoCursor:
    """Wrap a libSQL cursor so fetches return :class:`_TursoRow` objects."""

    def __init__(self, cursor) -> None:
        self._cursor = cursor
        self.lastrowid = getattr(cursor, "lastrowid", None)

    def _columns(self) -> list[str]:
        return [column[0] for column in (self._cursor.description or [])]

    def fetchone(self):
        row = self._cursor.fetchone()
        if row is None:
            return None
        return _TursoRow(self._columns(), row)

    def fetchall(self) -> list:
        columns = self._columns()
        return [_TursoRow(columns, row) for row in self._cursor.fetchall()]

    def __iter__(self):
        # libSQL cursors are not directly iterable, so materialise via fetchall.
        columns = self._columns()
        for row in self._cursor.fetchall():
            yield _TursoRow(columns, row)


class _TursoConnection:
    """Adapt a libSQL connection to the sqlite3 API the app relies on."""

    def __init__(self, connection) -> None:
        self._connection = connection

    def execute(self, sql: str, parameters=None) -> _TursoCursor:
        try:
            if parameters is None:
                cursor = self._connection.execute(sql)
            else:
                cursor = self._connection.execute(sql, parameters)
        except ValueError as error:
            # libSQL signals constraint failures as ValueError; re-raise as the
            # sqlite3 type so existing ``except sqlite3.IntegrityError`` works.
            if "constraint failed" in str(error).lower():
                raise sqlite3.IntegrityError(str(error)) from error
            raise
        return _TursoCursor(cursor)

    def executescript(self, script: str):
        return self._connection.executescript(script)

    def commit(self):
        return self._connection.commit()

    def rollback(self):
        return self._connection.rollback()

    def close(self):
        return self._connection.close()


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

    In production (``TURSO_DATABASE_URL`` set) this returns a libSQL connection
    wrapped to speak the same sqlite3 API; otherwise a local SQLite file is used.
    """
    if USE_TURSO:
        import libsql

        connection = _TursoConnection(
            libsql.connect(
                database=TURSO_DATABASE_URL,
                auth_token=TURSO_AUTH_TOKEN,
            )
        )
        try:
            connection.execute("PRAGMA foreign_keys = ON")
        except Exception:
            # Not fatal: Turso enforces FK behavior server-side and some builds
            # reject the PRAGMA over the remote protocol.
            pass
        return connection

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
