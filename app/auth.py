"""Google OAuth sign-in and the current-user dependency.

Sign-in uses Google as an OpenID Connect provider through Authlib: the token
exchange and id-token validation are handled by the library rather than by hand.
The signed-in user is kept in the request session (a signed cookie set up by
``SessionMiddleware``); ``get_current_user`` reads it, so protected routes never
touch the database just to identify the caller.
"""

import os
import sqlite3

from authlib.integrations.starlette_client import OAuth
from fastapi import HTTPException, Request, status


GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()
GOOGLE_METADATA_URL = "https://accounts.google.com/.well-known/openid-configuration"


oauth = OAuth()
oauth.register(
    name="google",
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    server_metadata_url=GOOGLE_METADATA_URL,
    client_kwargs={"scope": "openid email profile"},
)


def upsert_user(connection: sqlite3.Connection, claims: dict) -> dict:
    """Insert or refresh the signed-in Google user; return the stored record.

    Google's ``sub`` is the stable identifier: the email or display name may
    change, so those are updated on every sign-in while ``sub`` keys the row.
    """
    sub = claims["sub"]
    email = claims.get("email", "")
    name = claims.get("name")
    picture = claims.get("picture")

    connection.execute(
        """
        INSERT INTO users (google_sub, email, name, picture)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(google_sub) DO UPDATE SET
            email = excluded.email,
            name = excluded.name,
            picture = excluded.picture
        """,
        (sub, email, name, picture),
    )
    connection.commit()

    row = connection.execute(
        "SELECT id, email, name, picture FROM users WHERE google_sub = ?",
        (sub,),
    ).fetchone()
    return {
        "id": row["id"],
        "email": row["email"],
        "name": row["name"],
        "picture": row["picture"],
    }


def get_current_user(request: Request) -> dict:
    """Return the signed-in user or raise 401.

    Depend on this from any route that must be private. Tests override it through
    ``app.dependency_overrides`` so they can exercise the API without a real
    Google round-trip.
    """
    user = request.session.get("user")
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sign in with Google to continue.",
        )
    return user


def optional_user(request: Request) -> dict | None:
    """Return the signed-in user if there is one, otherwise ``None``.

    Used by the home page, which renders a sign-in prompt rather than a 401 when
    nobody is signed in.
    """
    return request.session.get("user")
