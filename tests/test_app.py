from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_returns_application_status() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "app": "StudyDeck"}


def test_home_page_renders() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "StudyDeck" in response.text
    assert "Flashcards that return at the right time" in response.text

