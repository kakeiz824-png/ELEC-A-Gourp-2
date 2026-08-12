"""Tag endpoints: list tags with book counts for the filter bar."""

import sqlite3

from fastapi import APIRouter, Depends

from app.auth import get_current_user
from app.db import get_db
from app.models import Tag


router = APIRouter(prefix="/tags", tags=["tags"])


@router.get("", response_model=list[Tag])
def list_tags(
    user: dict = Depends(get_current_user),
    connection: sqlite3.Connection = Depends(get_db),
) -> list[dict]:
    """The caller's own tags, with how many of their books carry each.

    Scoped to the signed-in user for the same reason every book endpoint is: a
    tag row is shared by name across users (so two readers filing books under
    "Non-fiction" reuse one row), but *whose* books carry it is private. Counting
    every user's ``book_tags`` would put another reader's categories in this
    reader's filter bar, showing a count that ``GET /books?tag=`` -- which is
    scoped -- then answers with nothing.

    The joins are inner rather than outer for the same reason: a tag carried
    only by other readers' books must not appear at all, not appear with a
    count of zero.
    """
    rows = connection.execute(
        """
        SELECT t.id, t.name, COUNT(bt.book_id) AS count
        FROM tags t
        JOIN book_tags bt ON bt.tag_id = t.id
        JOIN books b ON b.id = bt.book_id
        WHERE b.user_id = ?
        GROUP BY t.id
        ORDER BY t.name COLLATE NOCASE
        """,
        (user["id"],),
    ).fetchall()
    return [
        {"id": row["id"], "name": row["name"], "count": row["count"]}
        for row in rows
    ]
