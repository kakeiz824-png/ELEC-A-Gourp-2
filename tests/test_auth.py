"""Sign-in, session, and per-user isolation.

The rest of the suite runs as a fixed signed-in user via the autouse ``signed_in``
override in ``conftest.py``. These tests instead exercise the auth boundary
itself: the Google redirect, the callback that opens a session, sign-out, the
401 shown to anonymous callers, and the guarantee that one user never sees
another's books. The real Google round-trip is replaced with a stub so no test
touches the network.
"""

import pytest
from fastapi.responses import RedirectResponse

from app.auth import get_current_user, optional_user
from app.db import get_connection
from app.main import app
from app.routers import auth as auth_router


USER_ONE = {"id": 1, "email": "one@example.com", "name": "User One", "picture": None}
USER_TWO = {"id": 2, "email": "two@example.com", "name": "User Two", "picture": None}


@pytest.fixture()
def anon_client(client):
    """A client with no signed-in user: the auth overrides are removed so the
    real session-backed dependencies decide who (if anyone) is signed in."""
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(optional_user, None)
    return client


def _add_user_two() -> None:
    connection = get_connection()
    try:
        connection.execute(
            "INSERT INTO users (id, google_sub, email) VALUES (2, 'sub-2', 'two@example.com')"
        )
        connection.commit()
    finally:
        connection.close()


# --- The Google handshake -------------------------------------------------


def test_login_redirects_to_google(client, monkeypatch) -> None:
    async def fake_redirect(request, redirect_uri):
        return RedirectResponse(url="https://accounts.google.com/o/oauth2/v2/auth?stub=1")

    monkeypatch.setattr(auth_router.oauth.google, "authorize_redirect", fake_redirect)

    response = client.get("/login", follow_redirects=False)

    assert response.status_code in (302, 307)
    assert "accounts.google.com" in response.headers["location"]


def test_callback_creates_the_user_and_opens_a_session(anon_client, monkeypatch) -> None:
    async def fake_token(request):
        return {
            "userinfo": {
                "sub": "google-abc",
                "email": "new@example.com",
                "name": "New Reader",
                "picture": "https://example.com/p.png",
            }
        }

    monkeypatch.setattr(auth_router.oauth.google, "authorize_access_token", fake_token)

    response = anon_client.get(
        "/auth/callback?code=abc&state=xyz", follow_redirects=False
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/"

    # The session cookie now identifies the user: the home nav shows their name
    # and a protected endpoint answers instead of 401.
    home = anon_client.get("/")
    assert "New Reader" in home.text
    assert anon_client.get("/books").status_code == 200


def test_logout_clears_the_session(anon_client, monkeypatch) -> None:
    async def fake_token(request):
        return {"userinfo": {"sub": "google-abc", "email": "e@example.com", "name": "E"}}

    monkeypatch.setattr(auth_router.oauth.google, "authorize_access_token", fake_token)
    anon_client.get("/auth/callback?code=abc&state=xyz", follow_redirects=False)
    assert anon_client.get("/books").status_code == 200

    logout = anon_client.get("/logout", follow_redirects=False)
    assert logout.status_code == 303

    # With the session cleared the caller is anonymous again.
    assert anon_client.get("/books").status_code == 401


# --- The anonymous boundary ----------------------------------------------


def test_protected_endpoints_require_sign_in(anon_client) -> None:
    assert anon_client.get("/books").status_code == 401
    assert anon_client.get("/stats").status_code == 401
    assert anon_client.post("/books", json={"title": "The Hobbit"}).status_code == 401
    # The filter bar describes the caller's own library, so it is private too.
    assert anon_client.get("/tags").status_code == 401
    assert anon_client.get("/recommendations").status_code == 401


def test_home_shows_sign_in_when_signed_out(anon_client) -> None:
    text = anon_client.get("/").text
    assert "Sign in with Google" in text
    # The tracker UI (its search form) is not rendered while signed out.
    assert 'id="add-form"' not in text


# --- Per-user isolation ---------------------------------------------------


def test_users_do_not_see_each_others_books(client) -> None:
    _add_user_two()

    app.dependency_overrides[get_current_user] = lambda: USER_ONE
    created = client.post("/books", json={"title": "The Hobbit"})
    assert created.status_code == 201
    book_id = created.json()["id"]
    assert len(client.get("/books").json()) == 1

    # User two has an empty library and cannot read user one's book by id.
    app.dependency_overrides[get_current_user] = lambda: USER_TWO
    assert client.get("/books").json() == []
    assert client.get(f"/books/{book_id}").status_code == 404
    assert client.patch(
        f"/books/{book_id}/shelf", json={"shelf": "finished"}
    ).status_code == 404
    assert client.delete(f"/books/{book_id}").status_code == 404


def test_the_same_isbn_is_independent_per_user(client) -> None:
    _add_user_two()

    app.dependency_overrides[get_current_user] = lambda: USER_ONE
    assert client.post("/books", json={"title": "The Hobbit"}).status_code == 201

    # The same book added by another user is a new row, not a 409 duplicate.
    app.dependency_overrides[get_current_user] = lambda: USER_TWO
    assert client.post("/books", json={"title": "The Hobbit"}).status_code == 201
    assert len(client.get("/books").json()) == 1
