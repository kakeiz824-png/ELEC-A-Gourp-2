"""Recommendation endpoint tests: category ranking, exclusion, and graceful empties.

The recommendation strip suggests unread books in the categories the reader reads
most. These tests drive it through the API, mocking the catalogue's subject
search so none of them touch the real Open Library.
"""

import httpx


def _finish_tagged(client, title: str, tags: list[str]) -> dict:
    """Add a book to the finished shelf and tag it, through the offline seed."""
    book = client.post("/books", json={"title": title, "shelf": "finished"}).json()
    resp = client.put(f"/books/{book['id']}/tags", json={"tags": tags})
    assert resp.status_code == 200, resp.text
    return book


# A subject search response with three sci-fi books, one of which the reader
# already owns (The Hobbit, from the seed) so exclusion can be checked.
SUBJECT_DOCS = {
    "numFound": 3,
    "docs": [
        {
            "title": "The Hobbit",
            "author_name": ["J. R. R. Tolkien"],
            "isbn": ["9780261103344"],
            "first_publish_year": 1937,
        },
        {
            "title": "Neuromancer",
            "author_name": ["William Gibson"],
            "isbn": ["9780441569595"],
            "first_publish_year": 1984,
        },
        {
            "title": "Foundation",
            "author_name": ["Isaac Asimov"],
            "isbn": ["9780553293357"],
            "first_publish_year": 1951,
        },
    ],
}


def test_recommends_unread_books_in_a_read_category(client, mock_openlibrary) -> None:
    """A finished, categorised book yields catalogue books in that category."""
    _finish_tagged(client, "The Hobbit", ["Sci-Fi & Fantasy"])

    mock_openlibrary(lambda request: httpx.Response(200, json=SUBJECT_DOCS))

    recs = client.get("/recommendations").json()

    titles = [rec["title"] for rec in recs]
    # The reader already owns The Hobbit, so it is excluded from its own category.
    assert titles == ["Neuromancer", "Foundation"]
    assert all(rec["category"] == "Sci-Fi & Fantasy" for rec in recs)
    assert all(rec["isbn"] for rec in recs)


def test_the_limit_bounds_how_many_are_returned(client, mock_openlibrary) -> None:
    _finish_tagged(client, "Dune", ["Sci-Fi & Fantasy"])

    mock_openlibrary(lambda request: httpx.Response(200, json=SUBJECT_DOCS))

    recs = client.get("/recommendations", params={"limit": 1}).json()

    assert len(recs) == 1


def test_free_form_tags_do_not_drive_recommendations(
    client, mock_openlibrary
) -> None:
    """A tag that names no known category never reaches the catalogue."""
    _finish_tagged(client, "The Hobbit", ["2026", "loaned to Sam"])

    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("the catalogue must not be queried without a category")

    mock_openlibrary(handler)

    assert client.get("/recommendations").json() == []


def test_wishlist_books_do_not_count_as_read(client, mock_openlibrary) -> None:
    """A category only on the wishlist is not something the reader has read."""
    book = client.post(
        "/books", json={"title": "Dune", "shelf": "wishlist"}
    ).json()
    client.put(f"/books/{book['id']}/tags", json={"tags": ["Sci-Fi & Fantasy"]})

    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("a wishlist category must not drive recommendations")

    mock_openlibrary(handler)

    assert client.get("/recommendations").json() == []


def test_no_recommendations_for_an_empty_library(client) -> None:
    assert client.get("/recommendations").json() == []


def test_recommendations_are_empty_when_the_catalogue_is_offline(client) -> None:
    """The seed backend has no subject search, so recommendations quietly empty."""
    _finish_tagged(client, "The Hobbit", ["Sci-Fi & Fantasy"])

    assert client.get("/recommendations").json() == []
