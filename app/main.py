"""Shelf Life FastAPI entry point."""

import os
import secrets
import sqlite3
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app.auth import get_current_user, optional_user
from app.db import get_db, init_db
from app.models import Stats
from app.routers import auth, authors, books, reviews
from app.services.stats import collect_stats


# The session cookie is signed with this secret. A stable value is required in
# production (set SESSION_SECRET) so sessions survive restarts; a random fallback
# keeps local dev and tests working without configuration.
SESSION_SECRET = os.environ.get("SESSION_SECRET") or secrets.token_urlsafe(32)
# Send the session cookie only over HTTPS in production. Set SESSION_HTTPS_ONLY=1
# on the deployed service; left off so local http://127.0.0.1 dev still works.
SESSION_HTTPS_ONLY = os.environ.get("SESSION_HTTPS_ONLY", "").strip() in {"1", "true", "True"}


BASE_DIR = Path(__file__).resolve().parent.parent

DEFAULT_ORIGINS = "http://127.0.0.1:8000,http://localhost:8000"
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("SHELF_LIFE_ORIGINS", DEFAULT_ORIGINS).split(",")
    if origin.strip()
]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    init_db()
    yield


app = FastAPI(
    title="Shelf Life",
    description="A personal reading tracker: add a book by typing only its title.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Content-Type"],
)

# SessionMiddleware backs request.session, which both the OAuth handshake and the
# signed-in user record rely on. same_site="lax" lets the cookie ride along on
# the top-level redirect back from Google while still blocking cross-site POSTs.
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    same_site="lax",
    https_only=SESSION_HTTPS_ONLY,
)

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

app.include_router(auth.router)
app.include_router(books.router)
app.include_router(reviews.router)
app.include_router(authors.router)


@app.get("/", response_class=HTMLResponse)
async def home(
    request: Request,
    user: dict | None = Depends(optional_user),
) -> HTMLResponse:
    """Render the three-shelf reading tracker, or a sign-in prompt when signed out."""
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"app_name": "Shelf Life", "user": user},
    )


@app.get("/stats", response_model=Stats, tags=["stats"])
def stats(
    user: dict = Depends(get_current_user),
    connection: sqlite3.Connection = Depends(get_db),
) -> dict:
    """Reading statistics for the signed-in user: counts per shelf and average rating."""
    return collect_stats(connection, user["id"])


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    """Return a lightweight health check for local and hosted environments."""
    return {"status": "ok", "app": "Shelf Life"}
