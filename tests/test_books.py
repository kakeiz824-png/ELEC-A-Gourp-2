from concurrent.futures import ThreadPoolExecutor

import app.routers.books as books_router
from app.db import get_connection


def test_health_returns_application_status(client) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "app": "Shelf Life"}


def test_home_page_renders_three_shelves(client) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "Shelf Life" in response.text
    assert "Reading" in response.text
    assert "Finished" in response.text
    assert "Wishlist" in response.text


def test_the_demo_input_produces_an_auto_filled_card(client) -> None:
    """POST /books {title} is the magic moment; nothing else is typed."""
    response = client.post("/books", json={"title": "The Hobbit"})

    assert response.status_code == 201
    book = response.json()
    assert book["title"] == "The Hobbit"
    assert book["author"] == "J. R. R. Tolkien"
    assert book["year"] == 1937
    assert book["isbn"] == "9780261103344"
    assert book["cover_url"]
    assert book["shelf"] == "reading"
    assert book["details_pending"] is False


def test_shelves_start_empty(client) -> None:
    response = client.get("/books")

    assert response.status_code == 200
    assert response.json() == []


def test_a_book_can_be_added_straight_to_another_shelf(client) -> None:
    response = client.post("/books", json={"title": "Dune", "shelf": "wishlist"})

    assert response.status_code == 201
    assert response.json()["shelf"] == "wishlist"


def test_books_can_be_filtered_by_shelf(client) -> None:
    client.post("/books", json={"title": "The Hobbit"})
    client.post("/books", json={"title": "Dune", "shelf": "wishlist"})

    reading = client.get("/books", params={"shelf": "reading"}).json()
    wishlist = client.get("/books", params={"shelf": "wishlist"}).json()

    assert [book["title"] for book in reading] == ["The Hobbit"]
    assert [book["title"] for book in wishlist] == ["Dune"]


def test_an_unknown_shelf_filter_is_rejected(client) -> None:
    response = client.get("/books", params={"shelf": "someday"})

    assert response.status_code == 422


def test_an_unknown_title_is_still_saved_as_pending(client) -> None:
    response = client.post("/books", json={"title": "A Title Nobody Seeded"})

    assert response.status_code == 201
    book = response.json()
    assert book["title"] == "A Title Nobody Seeded"
    assert book["author"] is None
    assert book["details_pending"] is True


def test_a_lookup_outage_does_not_fail_the_add(client, monkeypatch) -> None:
    def explode(title: str):
        raise RuntimeError("Open Library is unreachable")

    monkeypatch.setattr(books_router, "lookup", explode)

    response = client.post("/books", json={"title": "The Hobbit"})

    assert response.status_code == 201
    assert response.json()["details_pending"] is True


def test_a_pending_book_can_be_enriched_later(client, monkeypatch) -> None:
    real_lookup = books_router.lookup

    def explode(title: str):
        raise RuntimeError("Open Library is unreachable")

    monkeypatch.setattr(books_router, "lookup", explode)
    book_id = client.post("/books", json={"title": "The Hobbit"}).json()["id"]
    monkeypatch.setattr(books_router, "lookup", real_lookup)

    response = client.post(f"/books/{book_id}/enrich")

    assert response.status_code == 200
    book = response.json()
    assert book["author"] == "J. R. R. Tolkien"
    assert book["details_pending"] is False


def test_a_blank_title_is_rejected(client) -> None:
    assert client.post("/books", json={"title": "   "}).status_code == 422
    assert client.post("/books", json={"title": ""}).status_code == 422


def test_a_book_can_be_moved_between_shelves(client) -> None:
    book_id = client.post("/books", json={"title": "The Hobbit"}).json()["id"]

    response = client.patch(f"/books/{book_id}/shelf", json={"shelf": "finished"})

    assert response.status_code == 200
    assert response.json()["shelf"] == "finished"
    assert client.get(f"/books/{book_id}").json()["shelf"] == "finished"


def test_an_invalid_shelf_move_is_rejected(client) -> None:
    book_id = client.post("/books", json={"title": "The Hobbit"}).json()["id"]

    response = client.patch(f"/books/{book_id}/shelf", json={"shelf": "abandoned"})

    assert response.status_code == 422


def test_a_book_can_be_fetched_with_its_reviews(client) -> None:
    book_id = client.post("/books", json={"title": "The Hobbit"}).json()["id"]
    client.post(f"/books/{book_id}/reviews", json={"rating": 5, "text": "A comfort read."})

    response = client.get(f"/books/{book_id}")

    assert response.status_code == 200
    body = response.json()
    assert len(body["reviews"]) == 1
    assert body["reviews"][0]["rating"] == 5


def test_a_book_can_be_deleted(client) -> None:
    book_id = client.post("/books", json={"title": "The Hobbit"}).json()["id"]

    assert client.delete(f"/books/{book_id}").status_code == 204
    assert client.get(f"/books/{book_id}").status_code == 404
    assert client.get("/books").json() == []


def test_missing_books_return_404(client) -> None:
    assert client.get("/books/999").status_code == 404
    assert client.delete("/books/999").status_code == 404
    assert client.patch("/books/999/shelf", json={"shelf": "finished"}).status_code == 404


def test_stats_summarise_the_shelves(client) -> None:
    client.post("/books", json={"title": "The Hobbit"})
    dune_id = client.post("/books", json={"title": "Dune", "shelf": "wishlist"}).json()["id"]
    client.post(f"/books/{dune_id}/reviews", json={"rating": 4})

    stats = client.get("/stats").json()

    assert stats["total"] == 2
    assert stats["by_shelf"] == {"reading": 1, "finished": 0, "wishlist": 1}
    assert stats["review_count"] == 1
    assert stats["average_rating"] == 4.0


def test_a_connection_can_cross_threads(client) -> None:
    """FastAPI may run the get_db dependency and the endpoint on different workers,
    so a connection has to survive being handed to another thread."""
    connection = get_connection()
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            count = pool.submit(
                lambda: connection.execute("SELECT COUNT(*) AS c FROM books").fetchone()["c"]
            ).result()
    finally:
        connection.close()

    assert count == 0


def test_stats_are_empty_before_any_book_is_added(client) -> None:
    stats = client.get("/stats").json()

    assert stats["total"] == 0
    assert stats["average_rating"] is None
