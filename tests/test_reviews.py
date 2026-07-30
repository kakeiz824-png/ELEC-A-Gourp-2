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


def test_a_second_review_updates_the_existing_personal_review(client, book_id) -> None:
    first = client.post(
        f"/books/{book_id}/reviews", json={"rating": 4, "text": "First note"}
    )
    updated = client.post(
        f"/books/{book_id}/reviews", json={"rating": 2, "text": "Updated note"}
    )

    response = client.get(f"/books/{book_id}/reviews")

    assert first.status_code == 201
    assert updated.status_code in (200, 201)
    assert updated.json()["id"] == first.json()["id"]
    assert response.status_code == 200
    assert response.json() == [updated.json()]
    assert updated.json()["rating"] == 2
    assert updated.json()["text"] == "Updated note"


def test_repeating_the_same_review_does_not_create_a_duplicate(client, book_id) -> None:
    payload = {"rating": 5, "text": "Only store this once."}

    first = client.post(f"/books/{book_id}/reviews", json=payload)
    repeated = client.post(f"/books/{book_id}/reviews", json=payload)

    assert repeated.status_code in (200, 201)
    assert repeated.json()["id"] == first.json()["id"]
    assert len(client.get(f"/books/{book_id}/reviews").json()) == 1


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
