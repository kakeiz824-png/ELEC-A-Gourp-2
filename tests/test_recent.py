def test_recent_returns_newest_first(client) -> None:
    created = [
        client.post("/books", json={"title": title}).json()["title"]
        for title in ["The Hobbit", "Dune", "Nineteen Eighty-Four"]
    ]

    titles = [book["title"] for book in client.get("/books/recent").json()]

    assert titles == list(reversed(created))


def test_recent_respects_limit(client) -> None:
    created = [
        client.post("/books", json={"title": title}).json()["title"]
        for title in ["The Hobbit", "Dune", "Nineteen Eighty-Four"]
    ]

    results = client.get("/books/recent", params={"limit": 2}).json()

    assert [book["title"] for book in results] == list(reversed(created))[:2]


def test_recent_defaults_to_five(client) -> None:
    for title in [
        "The Hobbit",
        "The Lord of the Rings",
        "Nineteen Eighty-Four",
        "Dune",
        "Pride and Prejudice",
        "The Little Prince",
        "Sapiens: A Brief History of Humankind",
    ]:
        client.post("/books", json={"title": title})

    assert len(client.get("/books/recent").json()) == 5


def test_recent_on_empty_library_returns_empty_list(client) -> None:
    response = client.get("/books/recent")

    assert response.status_code == 200
    assert response.json() == []


def test_recent_rejects_out_of_range_limit(client) -> None:
    assert client.get("/books/recent", params={"limit": 0}).status_code == 422
    assert client.get("/books/recent", params={"limit": 51}).status_code == 422


def test_recent_does_not_shadow_book_detail_route(client) -> None:
    """`/books/recent` must not swallow `/books/{id}`."""
    created = client.post("/books", json={"title": "Dune"}).json()

    response = client.get(f"/books/{created['id']}")

    assert response.status_code == 200
    assert response.json()["title"] == "Dune"
