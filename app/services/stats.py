"""Reading statistics."""

import sqlite3

from app.db import SHELVES


def collect_stats(connection: sqlite3.Connection) -> dict:
    """Count books per shelf and summarise ratings."""
    by_shelf = {shelf: 0 for shelf in SHELVES}
    for row in connection.execute(
        "SELECT shelf, COUNT(*) AS count FROM books GROUP BY shelf"
    ):
        by_shelf[row["shelf"]] = row["count"]

    row = connection.execute(
        "SELECT COUNT(*) AS count, AVG(rating) AS average FROM reviews"
    ).fetchone()
    average = row["average"]

    return {
        "total": sum(by_shelf.values()),
        "by_shelf": by_shelf,
        "review_count": row["count"],
        "average_rating": round(average, 2) if average is not None else None,
    }
