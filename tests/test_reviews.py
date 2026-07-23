import pytest

from app.db import get_connection


@pytest.fixture()
def book_id(client) -> int:
    return client.post("/books", json={"title": "The Hobbit"}).json()["id"]


def test_a_review_can_be_added_to_a_book(client, book_id) -> None:
    response = client.post(
        f"/books/{book_id}/reviews", json={"rating": 5, "text": "Still the best."}
    )

    assert response.status_code == 201
    review = response.json()
    assert review["book_id"] == book_id
    assert review["rating"] == 5
    assert review["text"] == "Still the best."


def test_review_text_is_optional(client, book_id) -> None:
    response = client.post(f"/books/{book_id}/reviews", json={"rating": 3})

    assert response.status_code == 201
    assert response.json()["text"] is None


def test_a_book_may_have_many_reviews(client, book_id) -> None:
    client.post(f"/books/{book_id}/reviews", json={"rating": 4})
    client.post(f"/books/{book_id}/reviews", json={"rating": 2})

    response = client.get(f"/books/{book_id}/reviews")

    assert response.status_code == 200
    assert len(response.json()) == 2


@pytest.mark.parametrize("rating", [0, 6, -1, 100])
def test_a_rating_outside_one_to_five_is_rejected(client, book_id, rating) -> None:
    response = client.post(f"/books/{book_id}/reviews", json={"rating": rating})

    assert response.status_code == 422


def test_a_missing_rating_is_rejected(client, book_id) -> None:
    response = client.post(f"/books/{book_id}/reviews", json={"text": "No stars given."})

    assert response.status_code == 422


def test_reviewing_a_missing_book_returns_404(client) -> None:
    response = client.post("/books/999/reviews", json={"rating": 5})

    assert response.status_code == 404


def test_listing_reviews_for_a_missing_book_returns_404(client) -> None:
    assert client.get("/books/999/reviews").status_code == 404


def test_deleting_a_book_deletes_its_reviews(client, book_id) -> None:
    """ON DELETE CASCADE only fires because each connection enables foreign keys."""
    client.post(f"/books/{book_id}/reviews", json={"rating": 5})
    client.delete(f"/books/{book_id}")

    connection = get_connection()
    try:
        remaining = connection.execute(
            "SELECT COUNT(*) AS count FROM reviews WHERE book_id = ?", (book_id,)
        ).fetchone()["count"]
    finally:
        connection.close()

    assert remaining == 0
