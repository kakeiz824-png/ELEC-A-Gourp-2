"""Regression tests for the libSQL/Turso compatibility layer in app.db.

These exercise the ``_TursoConnection`` wrapper against a real in-memory libSQL
engine (``libsql.connect(":memory:")``), which behaves like the remote Turso
connection used in production. The rest of the suite runs on plain sqlite3,
where cursors are iterable and rows already support name access, so it cannot
catch Turso-only regressions such as a cursor that is not directly iterable.
"""

import sqlite3

import pytest

import app.db as db

libsql = pytest.importorskip("libsql")


@pytest.fixture()
def turso_conn():
    """A wrapped in-memory libSQL connection with the app schema applied."""
    connection = db._TursoConnection(libsql.connect(":memory:"))
    connection.executescript(db.SCHEMA)
    db._migrate_unique_books(connection)
    db._migrate_single_user_reviews(connection)
    connection.commit()
    yield connection
    connection.close()


def _insert_book(connection, *, title, isbn, shelf="reading"):
    cursor = connection.execute(
        "INSERT INTO books (title, author, isbn, cover_url, year, shelf, "
        "details_pending, identity_key) VALUES (?,?,?,?,?,?,?,?)",
        (title, None, isbn, None, None, shelf, 0, f"isbn:{isbn}"),
    )
    connection.commit()
    return cursor.lastrowid


def test_named_row_and_lastrowid(turso_conn):
    book_id = _insert_book(turso_conn, title="Dune", isbn="9780441172719")
    assert isinstance(book_id, int)
    row = turso_conn.execute(
        "SELECT * FROM books WHERE id = ?", (book_id,)
    ).fetchone()
    assert row["title"] == "Dune"
    assert row["shelf"] == "reading"
    assert dict(row)["isbn"] == "9780441172719"


def test_cursor_is_iterable(turso_conn):
    # This is the exact pattern collect_stats() uses and the one that regressed:
    # `for row in connection.execute(...)`.
    _insert_book(turso_conn, title="A", isbn="1111111111111", shelf="reading")
    _insert_book(turso_conn, title="B", isbn="2222222222222", shelf="finished")
    counts = {}
    for row in turso_conn.execute(
        "SELECT shelf, COUNT(*) AS count FROM books GROUP BY shelf"
    ):
        counts[row["shelf"]] = row["count"]
    assert counts == {"reading": 1, "finished": 1}


def test_collect_stats_over_turso(turso_conn):
    from app.services.stats import collect_stats

    _insert_book(turso_conn, title="A", isbn="1111111111111", shelf="reading")
    stats = collect_stats(turso_conn)
    assert stats["total"] == 1
    assert stats["by_shelf"]["reading"] == 1
    assert stats["average_rating"] is None


def test_unique_violation_raises_integrity_error(turso_conn):
    _insert_book(turso_conn, title="Dune", isbn="9780441172719")
    with pytest.raises(sqlite3.IntegrityError):
        _insert_book(turso_conn, title="Dune again", isbn="9780441172719")
