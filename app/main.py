"""Shelf Life FastAPI entry point."""

import os
import sqlite3
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.db import get_db, init_db
from app.models import Stats
from app.routers import books, reviews
from app.services.stats import collect_stats


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

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

app.include_router(books.router)
app.include_router(reviews.router)


@app.get("/", response_class=HTMLResponse)
async def home(request: Request) -> HTMLResponse:
    """Render the three-shelf reading tracker."""
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"app_name": "Shelf Life"},
    )


@app.get("/stats", response_model=Stats, tags=["stats"])
def stats(connection: sqlite3.Connection = Depends(get_db)) -> dict:
    """Reading statistics: counts per shelf and average rating."""
    return collect_stats(connection)


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    """Return a lightweight health check for local and hosted environments."""
    return {"status": "ok", "app": "Shelf Life"}
