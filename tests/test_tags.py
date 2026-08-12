"""Tag endpoint tests: setting, listing, filtering, validation, and cleanup."""

import sqlite3

import httpx

import app.routers.books as books_router
from app.db import get_connection


def _add(client, title: str, shelf: str = "reading") -> dict:
    """Add a book through the seeded offline lookup."""
    resp = client.post("/books", json={"title": title, "shelf": shelf})
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_books_start_without_tags(client) -> None:
    book = _add(client, "The Hobbit")

    assert book["tags"] == []


def test_tags_can_be_set_deduplicated_and_listed(client) -> None:
    book = _add(client, "The Hobbit")

    resp = client.put(
        f"/books/{book['id']}/tags",
        json={"tags": ["sci-fi", "2026", "sci-fi", "   "]},
    )

    assert resp.status_code == 200
    assert resp.json()["tags"] == ["2026", "sci-fi"]  # sorted case-insensitively

    tags = {tag["name"]: tag["count"] for tag in client.get("/tags").json()}
    assert tags == {"sci-fi": 1, "2026": 1}


def test_tag_filter_combines_with_shelf(client) -> None:
    reading = _add(client, "The Hobbit", "reading")
    finished = _add(client, "Sapiens", "finished")
    client.put(f"/books/{reading['id']}/tags", json={"tags": ["sci-fi"]})
    client.put(f"/books/{finished['id']}/tags", json={"tags": ["sci-fi"]})

    both = client.get("/books", params={"tag": "sci-fi"}).json()
    assert {book["id"] for book in both} == {reading["id"], finished["id"]}

    only_reading = client.get(
        "/books", params={"tag": "sci-fi", "shelf": "reading"}
    ).json()
    assert [book["id"] for book in only_reading] == [reading["id"]]

    assert client.get("/books", params={"tag": "missing"}).json() == []


def test_tags_are_case_insensitively_reused(client) -> None:
    first = _add(client, "The Hobbit")
    second = _add(client, "Sapiens")
    client.put(f"/books/{first['id']}/tags", json={"tags": ["Sci-Fi"]})
    client.put(f"/books/{second['id']}/tags", json={"tags": ["sci-fi"]})

    tags = client.get("/tags").json()
    assert len(tags) == 1
    assert tags[0]["name"] == "Sci-Fi"
    assert tags[0]["count"] == 2


def test_tag_length_and_count_limits_are_enforced(client) -> None:
    book = _add(client, "The Hobbit")

    resp = client.put(
        f"/books/{book['id']}/tags", json={"tags": ["x" * 51]}
    )
    assert resp.status_code == 422

    resp = client.put(
        f"/books/{book['id']}/tags",
        json={"tags": [f"tag-{i}" for i in range(21)]},
    )
    assert resp.status_code == 422


def test_deleting_a_book_removes_orphan_tags(client) -> None:
    keep = _add(client, "The Hobbit")
    drop = _add(client, "Sapiens")
    client.put(f"/books/{keep['id']}/tags", json={"tags": ["shared", "only-keep"]})
    client.put(f"/books/{drop['id']}/tags", json={"tags": ["shared", "only-drop"]})

    client.delete(f"/books/{drop['id']}")

    names = {tag["name"] for tag in client.get("/tags").json()}
    assert names == {"shared", "only-keep"}


def test_the_filter_bar_only_counts_the_callers_own_books(client) -> None:
    """Another reader's tags must never appear in this reader's filter bar.

    Tag rows are shared by name across users, so counting every ``book_tags`` row
    showed a category the caller owns nothing under -- a count that
    ``GET /books?tag=`` then answered with an empty shelf.
    """
    mine = _add(client, "The Hobbit")
    client.put(f"/books/{mine['id']}/tags", json={"tags": ["Sci-Fi & Fantasy"]})

    connection = get_connection()
    try:
        connection.execute(
            "INSERT INTO users (id, google_sub, email, name, picture) "
            "VALUES (2, 'other-sub', 'other@example.com', 'Other', NULL)"
        )
        cursor = connection.execute(
            "INSERT INTO books (user_id, title, shelf, details_pending, identity_key) "
            "VALUES (2, 'Sapiens', 'finished', 0, 'isbn:9780062316097')"
        )
        tag_cursor = connection.execute("INSERT INTO tags (name) VALUES ('Non-fiction')")
        connection.execute(
            "INSERT INTO book_tags (book_id, tag_id) VALUES (?, ?)",
            (cursor.lastrowid, tag_cursor.lastrowid),
        )
        connection.commit()
    finally:
        connection.close()

    tags = {tag["name"]: tag["count"] for tag in client.get("/tags").json()}

    assert tags == {"Sci-Fi & Fantasy": 1}


def test_a_shared_tag_counts_only_the_callers_books(client) -> None:
    """A tag two readers both use reports only how many of *your* books carry it."""
    mine = _add(client, "The Hobbit")
    client.put(f"/books/{mine['id']}/tags", json={"tags": ["Sci-Fi & Fantasy"]})

    shared_tag_id = client.get("/tags").json()[0]["id"]

    connection = get_connection()
    try:
        connection.execute(
            "INSERT INTO users (id, google_sub, email, name, picture) "
            "VALUES (2, 'other-sub', 'other@example.com', 'Other', NULL)"
        )
        cursor = connection.execute(
            "INSERT INTO books (user_id, title, shelf, details_pending, identity_key) "
            "VALUES (2, 'Dune', 'reading', 0, 'isbn:9780441013593')"
        )
        connection.execute(
            "INSERT INTO book_tags (book_id, tag_id) VALUES (?, ?)",
            (cursor.lastrowid, shared_tag_id),
        )
        connection.commit()
    finally:
        connection.close()

    tags = {tag["name"]: tag["count"] for tag in client.get("/tags").json()}

    assert tags == {"Sci-Fi & Fantasy": 1}


def test_tagging_a_missing_book_returns_404(client) -> None:
    resp = client.put("/books/9999/tags", json={"tags": ["x"]})

    assert resp.status_code == 404


def test_get_book_returns_its_tags(client) -> None:
    book = _add(client, "The Hobbit")
    client.put(f"/books/{book['id']}/tags", json={"tags": ["classic"]})

    data = client.get(f"/books/{book['id']}").json()

    assert data["tags"] == ["classic"]

def test_tag_suggestions_come_from_open_library(client, mock_openlibrary) -> None:
    """The tag editor can suggest subjects from the Open Library catalogue."""
    book = _add(client, "The Hobbit")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"numFound": 1, "docs": [{"subject": ["Science fiction", "Aliens"]}]},
        )

    mock_openlibrary(handler)

    resp = client.get(f"/books/{book['id']}/tag-suggestions")

    assert resp.status_code == 200
    assert resp.json()["categories"] == ["Sci-Fi & Fantasy"]


def test_tag_suggestions_are_empty_when_the_catalogue_is_offline(client) -> None:
    book = _add(client, "The Hobbit")

    resp = client.get(f"/books/{book['id']}/tag-suggestions")

    assert resp.status_code == 200
    assert resp.json()["categories"] == []


def test_tag_suggestions_for_a_missing_book_return_404(client) -> None:
    assert client.get("/books/9999/tag-suggestions").status_code == 404


def test_adding_a_book_auto_applies_catalogue_categories(
    client, mock_openlibrary
) -> None:
    """A newly added book is filed under its broad categories automatically."""

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "/api/books" in url:
            # Confirming the submitted ISBN before it is stored.
            return httpx.Response(
                200,
                json={
                    "ISBN:9780261103344": {
                        "title": "The Hobbit",
                        "authors": [{"name": "J. R. R. Tolkien"}],
                    }
                },
            )
        # The subject lookup behind the category suggestions.
        return httpx.Response(
            200, json={"numFound": 1, "docs": [{"subject": ["Science fiction"]}]}
        )

    mock_openlibrary(handler)

    resp = client.post(
        "/books", json={"title": "The Hobbit", "isbn": "9780261103344"}
    )

    assert resp.status_code == 201, resp.text
    assert resp.json()["tags"] == ["Sci-Fi & Fantasy"]


def test_auto_categorisation_never_blocks_an_add(client, mock_openlibrary) -> None:
    """If the subject lookup fails, the book is still added, just untagged."""

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "/api/books" in url:
            return httpx.Response(
                200,
                json={
                    "ISBN:9780261103344": {
                        "title": "The Hobbit",
                        "authors": [{"name": "J. R. R. Tolkien"}],
                    }
                },
            )
        raise httpx.ConnectError("subject index timeout")

    mock_openlibrary(handler)

    resp = client.post(
        "/books", json={"title": "The Hobbit", "isbn": "9780261103344"}
    )

    assert resp.status_code == 201, resp.text
    assert resp.json()["tags"] == []


def test_a_tag_write_failure_does_not_fail_the_add(
    client, mock_openlibrary, monkeypatch
) -> None:
    """A database error while writing auto-categories still leaves the book added.

    Reproduces the regression where the tag write sat outside the best-effort
    guard, so a transient lock during categorisation turned a successful add
    into a 500.
    """

    def boom(connection, book_id, names):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(books_router, "_replace_book_tags", boom)

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "/api/books" in url:
            return httpx.Response(
                200,
                json={
                    "ISBN:9780261103344": {
                        "title": "The Hobbit",
                        "authors": [{"name": "J. R. R. Tolkien"}],
                    }
                },
            )
        return httpx.Response(
            200, json={"numFound": 1, "docs": [{"subject": ["Science fiction"]}]}
        )

    mock_openlibrary(handler)

    resp = client.post(
        "/books", json={"title": "The Hobbit", "isbn": "9780261103344"}
    )

    assert resp.status_code == 201, resp.text
    assert resp.json()["tags"] == []
    # The book really is stored, not just reported as added.
    assert len(client.get("/books").json()) == 1