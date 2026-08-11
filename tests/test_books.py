from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import app.routers.books as books_router
import app.services.search as search_service
from app.db import get_connection
from app.details import BookDetails, SearchPage


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
    assert "/static/app.js?v=20260811-search-feedback" in response.text


def test_cover_placeholder_asset_is_served(client) -> None:
    response = client.get("/static/cover-placeholder.svg")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/svg+xml")
    assert "NO COVER" in response.text


def test_card_actions_report_failures() -> None:
    """Card actions go through cardAction so a failed request is never silent."""
    source = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text(
        encoding="utf-8"
    )

    assert "async function cardAction" in source
    assert "Could not move that book." in source
    assert "Could not delete that book." in source
    assert "Could not save your review." in source


def test_cover_fallback_detects_blank_images() -> None:
    """The browser script keeps the 1x1 transparent-image detection."""
    source = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text(
        encoding="utf-8"
    )

    assert "/static/cover-placeholder.svg" in source
    assert "naturalWidth" in source


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


def test_search_returns_selectable_isbn_candidates_without_storing(
    client, monkeypatch
) -> None:
    monkeypatch.setattr(
        search_service,
        "search_book",
        lambda title, **paging: SearchPage(
            total=8,
            results=[
                BookDetails(title="No ISBN"),
                BookDetails(title="Edition 1", isbn="1111111111"),
                BookDetails(title="Duplicate ISBN", isbn="111-111-111-1"),
                BookDetails(title="Edition 2", isbn="2222222222"),
                BookDetails(title="Edition 3", isbn="3333333333"),
            ],
        ),
    )

    response = client.get("/books/search", params={"title": "A title"})

    assert response.status_code == 200
    # No ISBN is unstorable, and the hyphenated duplicate is the same book.
    assert [book["isbn"] for book in response.json()["items"]] == [
        "1111111111",
        "2222222222",
        "3333333333",
    ]
    assert client.get("/books").json() == []


def test_the_user_selected_isbn_is_added_instead_of_the_first_candidate(
    client,
) -> None:
    """Two seeded books share nothing but a shelf; the submitted ISBN decides."""
    response = client.post(
        "/books",
        json={"title": "Dune", "isbn": "978-0-451-52493-5", "shelf": "wishlist"},
    )

    assert response.status_code == 201
    assert response.json()["title"] == "Nineteen Eighty-Four"
    assert response.json()["author"] == "George Orwell"
    assert response.json()["isbn"] == "9780451524935"
    assert response.json()["shelf"] == "wishlist"


def test_the_same_catalogue_book_is_not_added_to_two_shelves(client) -> None:
    first = client.post("/books", json={"title": "The Hobbit", "shelf": "reading"})
    duplicate = client.post(
        "/books", json={"title": "The Hobbit", "shelf": "wishlist"}
    )

    assert first.status_code == 201
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["code"] == "book_exists"
    assert duplicate.json()["detail"]["message"] == (
        "This book is already on your Reading shelf."
    )
    assert duplicate.json()["detail"]["book"]["id"] == first.json()["id"]
    assert duplicate.json()["detail"]["book"]["shelf"] == "reading"
    assert len(client.get("/books").json()) == 1


def test_title_case_and_surrounding_space_do_not_create_a_duplicate(client) -> None:
    first = client.post("/books", json={"title": "The Hobbit"})
    duplicate = client.post("/books", json={"title": "  the hobbit  "})

    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["book"]["id"] == first.json()["id"]
    assert len(client.get("/books").json()) == 1


def test_same_title_with_different_isbns_can_be_tracked(
    client, monkeypatch
) -> None:
    results = iter(
        (
            BookDetails(title="Shared Title", author="Author One", isbn="1111111111"),
            BookDetails(title="Shared Title", author="Author Two", isbn="2222222222"),
        )
    )
    monkeypatch.setattr(books_router, "lookup", lambda title: next(results))

    first = client.post("/books", json={"title": "Shared Title"})
    second = client.post(
        "/books", json={"title": "Shared Title", "shelf": "wishlist"}
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["isbn"] != second.json()["isbn"]
    assert len(client.get("/books").json()) == 2


def test_concurrent_adds_create_only_one_book(client) -> None:
    def add_hobbit(shelf: str):
        return client.post("/books", json={"title": "The Hobbit", "shelf": shelf})

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(add_hobbit, ("reading", "wishlist")))

    assert sorted(response.status_code for response in responses) == [201, 409]
    ids = {
        response.json()["id"]
        if response.status_code == 201
        else response.json()["detail"]["book"]["id"]
        for response in responses
    }
    assert len(ids) == 1
    assert len(client.get("/books").json()) == 1


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


def test_an_unknown_title_is_rejected_without_an_isbn(client) -> None:
    response = client.post("/books", json={"title": "A Title Nobody Seeded"})

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "isbn_not_found"
    assert client.get("/books").json() == []


def test_a_lookup_outage_does_not_create_a_book_without_an_isbn(
    client, monkeypatch
) -> None:
    def explode(title: str):
        raise RuntimeError("Open Library is unreachable")

    monkeypatch.setattr(books_router, "lookup", explode)

    response = client.post("/books", json={"title": "The Hobbit"})

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "isbn_not_found"
    assert client.get("/books").json() == []


def test_a_legacy_pending_book_can_be_enriched_later(client) -> None:
    connection = get_connection()
    try:
        cursor = connection.execute(
            """
            INSERT INTO books (title, shelf, details_pending, identity_key)
            VALUES ('The Hobbit', 'reading', 1, 'legacy:test-pending')
            """
        )
        connection.commit()
        book_id = cursor.lastrowid
    finally:
        connection.close()

    response = client.post(f"/books/{book_id}/enrich")

    assert response.status_code == 200
    book = response.json()
    assert book["author"] == "J. R. R. Tolkien"
    assert book["details_pending"] is False


def test_a_catalogue_result_without_an_isbn_is_rejected(
    client, monkeypatch
) -> None:
    monkeypatch.setattr(
        books_router,
        "lookup",
        lambda title: BookDetails(title="Real title", author="Known Author"),
    )

    response = client.post("/books", json={"title": "Real title"})

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "isbn_not_found"
    assert client.get("/books").json() == []


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
