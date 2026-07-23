import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """A client backed by a fresh database file per test."""
    monkeypatch.setenv("SHELF_LIFE_DB", str(tmp_path / "shelf_life.db"))
    with TestClient(app) as test_client:
        yield test_client
