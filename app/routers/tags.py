"""Tag endpoints: list tags with book counts for the filter bar."""

import sqlite3

from fastapi import APIRouter, Depends

from app.db import get_db
from app.models import Tag


router = APIRouter(prefix="/tags", tags=["tags"])


@router.get("", response_model=list[Tag])
def list_tags(connection: sqlite3.Connection = Depends(get_db)) -> list[dict]:
    """Every tag with how many books carry it, ordered by name."""
    rows = connection.execute(
        """
        SELECT t.id, t.name, COUNT(bt.book_id) AS count
        FROM tags t
        LEFT JOIN book_tags bt ON bt.tag_id = t.id
        GROUP BY t.id
        ORDER BY t.name COLLATE NOCASE
        """
    ).fetchall()
    return [
        {"id": row["id"], "name": row["name"], "count": row["count"]}
        for row in rows
    ]