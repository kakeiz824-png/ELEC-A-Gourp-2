import httpx
import pytest
from fastapi.testclient import TestClient

from app import openlibrary
from app.auth import get_current_user, optional_user
from app.db import get_connection
from app.lookup import clear_lookup_cache
from app.main import app


# The signed-in user every test acts as. Its id matches the row seeded into each
# fresh database, so books created through the API satisfy the user foreign key.
TEST_USER = {
    "id": 1,
    "email": "tester@example.com",
    "name": "Tester",
    "picture": None,
}


@pytest.fixture(autouse=True)
def signed_in():
    """Act as ``TEST_USER`` for every request, skipping the real Google flow.

    ``get_current_user`` is overridden rather than mocked so protected routes see
    a stable user without a token round-trip. ``tests/test_auth.py`` removes the
    override where it needs to exercise the signed-out (401) behaviour.
    """
    app.dependency_overrides[get_current_user] = lambda: TEST_USER
    app.dependency_overrides[optional_user] = lambda: TEST_USER
    yield
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(optional_user, None)


def seed_test_user(connection) -> None:
    """Insert ``TEST_USER`` (id=1) so book rows can reference it."""
    connection.execute(
        """
        INSERT INTO users (id, google_sub, email, name, picture)
        VALUES (1, 'test-google-sub', 'tester@example.com', 'Tester', NULL)
        """
    )
    connection.commit()


@pytest.fixture(autouse=True)
def offline_lookup(monkeypatch):
    """Keep every test off the real Open Library.

    Two belts: the lookup backend is pinned to the seed, and the HTTP client
    factory raises if anything reaches for it anyway.  A test that wants to
    exercise the Open Library path overrides both -- see ``test_openlibrary``.
    The live-lookup cache is cleared so a cached answer from one test can
    never leak into another.
    """
    clear_lookup_cache()
    monkeypatch.setenv("SHELF_LIFE_LOOKUP_BACKEND", "seed")

    def forbidden() -> httpx.Client:
        raise AssertionError(
            "A test tried to reach the real Open Library. Use mock_openlibrary."
        )

    monkeypatch.setattr(openlibrary, "client", forbidden)


@pytest.fixture()
def mock_openlibrary(monkeypatch):
    """Serve Open Library responses from a handler instead of the network.

    Call the returned function with a handler taking an ``httpx.Request`` and
    returning an ``httpx.Response``; it switches the lookup onto the Open
    Library backend and routes that backend's requests to the handler.
    """

    def install(handler) -> None:
        monkeypatch.setenv("SHELF_LIFE_LOOKUP_BACKEND", "openlibrary")
        monkeypatch.setattr(
            openlibrary,
            "client",
            lambda: httpx.Client(transport=httpx.MockTransport(handler)),
        )

    return install


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """A client backed by a fresh database file per test, seeded with the user."""
    monkeypatch.setenv("SHELF_LIFE_DB", str(tmp_path / "shelf_life.db"))
    with TestClient(app) as test_client:
        connection = get_connection()
        try:
            seed_test_user(connection)
        finally:
            connection.close()
        yield test_client
