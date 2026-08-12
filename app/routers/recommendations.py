"""Recommendation endpoint: unread books in the reader's most-read categories."""

import sqlite3

from fastapi import APIRouter, Depends, Query

from app.auth import get_current_user
from app.db import get_db
from app.models import Recommendation
from app.services import recommendations as recommend_service


router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.get("", response_model=list[Recommendation])
def list_recommendations(
    limit: int = Query(default=10, ge=1, le=50, description="How many to return"),
    user: dict = Depends(get_current_user),
    connection: sqlite3.Connection = Depends(get_db),
) -> list[dict]:
    """Suggest unread books in the categories the reader reads most.

    Content-based and best-effort: it reads the broad categories of the reader's
    own finished and reading books, asks the catalogue for other books under the
    top few, and excludes any the reader already tracks. An empty list is normal
    and not an error -- a new library, only free-form tags, or an offline
    catalogue all produce no suggestions.
    """
    return recommend_service.recommend(connection, user["id"], limit=limit)
