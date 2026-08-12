"""Sign-in, OAuth callback, and sign-out routes."""

import os
import sqlite3

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse

from app.auth import oauth, upsert_user
from app.db import get_db


router = APIRouter(tags=["auth"])


def redirect_uri(request: Request) -> str:
    """Where Google sends the user back after consent.

    A behind-a-proxy deployment (Render) can misreport its scheme, so an explicit
    ``OAUTH_REDIRECT_URI`` wins when set; locally it falls back to the callback
    route's own URL.
    """
    configured = os.environ.get("OAUTH_REDIRECT_URI", "").strip()
    if configured:
        return configured
    return str(request.url_for("auth_callback"))


@router.get("/login")
async def login(request: Request):
    """Start the Google sign-in flow."""
    return await oauth.google.authorize_redirect(request, redirect_uri(request))


@router.get("/auth/callback", name="auth_callback")
async def auth_callback(
    request: Request,
    connection: sqlite3.Connection = Depends(get_db),
):
    """Complete sign-in: exchange the code, upsert the user, open a session."""
    token = await oauth.google.authorize_access_token(request)
    claims = token.get("userinfo") or await oauth.google.userinfo(token=token)
    request.session["user"] = upsert_user(connection, claims)
    return RedirectResponse(url="/", status_code=303)


@router.get("/logout")
async def logout(request: Request):
    """Clear the session and return to the home page."""
    request.session.clear()
    return RedirectResponse(url="/", status_code=303)
