"""Author endpoint: the biography panel shown above an author's books.

Browsing an author's books is already answered by ``GET /books/search?author=``.
This router adds only the profile -- name, biography, life dates, and work count
-- which the book search does not carry. It is best-effort: a catalogue outage or
an author with no record yields ``found=false`` and null fields, so the browser
hides the panel rather than surfacing an error, and never calls Open Library
directly (the profile arrives through the same ``lookup`` boundary the rest of the
application uses).
"""

import logging

from fastapi import APIRouter, Query

from app.lookup import AuthorDetails, author_profile
from app.models import AuthorProfile


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/authors", tags=["authors"])


def safe_author_profile(name: str) -> AuthorDetails | None:
    """Look a profile up, treating any backend failure as no usable result."""
    try:
        return author_profile(name)
    except Exception:
        logger.warning("Author profile lookup failed for %r", name, exc_info=True)
        return None


@router.get("", response_model=AuthorProfile)
def get_author(
    name: str = Query(
        min_length=1, max_length=300, description="Author name to profile"
    ),
) -> dict:
    """Return one author's profile, or ``found=false`` when none is available."""
    details = safe_author_profile(name)
    if details is None:
        return {"name": name.strip(), "found": False}
    return {
        "name": details.name,
        "bio": details.bio,
        "birth_date": details.birth_date,
        "death_date": details.death_date,
        "work_count": details.work_count,
        "photo_url": details.photo_url,
        "found": True,
    }
