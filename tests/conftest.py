import httpx
import pytest
from fastapi.testclient import TestClient

from app import openlibrary
from app.lookup import clear_lookup_cache
from app.main import app


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
    """A client backed by a fresh database file per test."""
    monkeypatch.setenv("SHELF_LIFE_DB", str(tmp_path / "shelf_life.db"))
    with TestClient(app) as test_client:
        yield test_client
