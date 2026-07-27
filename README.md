Shelf Life Project Guide

## Project Overview

**Shelf Life** is a personal reading tracker that organizes books across three shelves: `reading`, `finished`, and `wishlist`. It includes ratings, optional review text, reading statistics, and automated book-detail enrichment. Enrichment queries the live Open Library API, with the offline seed in `seed/books.json` kept as the fallback when the catalogue cannot answer.

## Pitch and Core Philosophy

> A personal reading tracker with automated book metadata enrichment. The project uses a small, reliable data model so the team can focus on polish, testing, and safe external integration.

## Current Data Model

```text
+------------------------------------+         +-----------------------+
|                Book                | 1     * |        Review         |
+------------------------------------+---------+-----------------------+
| id: Integer                        |         | id: Integer           |
| title: String                      |         | book_id: FK -> Book   |
| author: String (optional)           |        | rating: Integer (1-5) |
| isbn: String (optional)             |        | text: String (optional)|
| shelf: reading|finished|wishlist    |        | created_at: Timestamp |
| cover_url: String (optional)        |        +-----------------------+
| year: Integer (optional)            |
| details_pending: Boolean            |
| created_at: Timestamp               |
+------------------------------------+
```

Both tables use SQLite integer primary keys. Deleting a book cascades to its reviews.

## Requirements and Scope (MoSCoW)

### Must Have

- **Book and shelf CRUD:** create, read, move, and delete books across `reading`, `finished`, and `wishlist`.
- **Book lookup:** fill author, ISBN, cover URL, and publication year from a title when a match is available.
- **Review and rating core:** create and read ratings and optional review text attached to a book.
- **Failure-safe add:** if lookup fails, save the typed title with `details_pending = 1`.

### Should Have

- **Reading statistics:** total books, counts per shelf, review count, and average rating.
- **Cover images:** display cover thumbnails when a cover URL is available.

### Could Have

- **Recommendation page:** selecting a book shows three related books. Early recommendations may use the same author or subject; collaborative "people who liked this also liked" recommendations require enough user activity data.
- **Book categories:** browse fiction categories (including mystery, science fiction, fantasy, romance, historical fiction, essays, poetry, drama, light novels, and comics) and nonfiction categories (including biography, business, psychology, humanities, social sciences, natural sciences, computing, practical life, language learning, art, design, and reference works).
- **Author library:** search for an author and browse their books and biography.
- **Accounts and chatrooms:** create personal accounts, add friends, create chatrooms, and share books and reviews. This requires authentication, authorization, privacy, moderation, and security work.
- **AI-assisted discovery:** find a book from a description of its content or features, or request recommendations from a description of the user's interests.
- **Reading challenges and rewards:** set daily, monthly, or seasonal reading goals, earn points for completing them, and display achievement tiers. Percentile-based tiers require sufficient active-user data; fixed thresholds can be used first.
- **Shared booklists:** create and share booklists containing personal reviews; other users can comment on and rate a shared list.
- **User profiles and privacy:** show a user's public booklists, liked books, and ratings, while allowing reviews and activity to be private, friends-only, or public.

These are future roadmap candidates, not a commitment to deliver all eight in M2. The team must select a small M2 subset after the required Open Library MCP integration, tests, and security scan are planned.

## Current API Endpoints

| Method | Endpoint | Description | Query or body |
| :--- | :--- | :--- | :--- |
| `GET` | `/` | Render the three-shelf web interface | N/A |
| `GET` | `/health` | Check whether the application is running | N/A |
| `GET` | `/books` | List books, optionally filtered by shelf | `?shelf=reading\|finished\|wishlist` |
| `POST` | `/books` | Add a book and attempt title lookup | `{ "title": "...", "shelf": "wishlist" }` |
| `GET` | `/books/{id}` | Get a book together with its reviews | N/A |
| `PATCH` | `/books/{id}/shelf` | Move a book to another shelf | `{ "shelf": "finished" }` |
| `POST` | `/books/{id}/enrich` | Retry lookup for a book | N/A |
| `DELETE` | `/books/{id}` | Delete a book and its reviews | N/A |
| `GET` | `/books/{id}/reviews` | List reviews for a book | N/A |
| `POST` | `/books/{id}/reviews` | Add a rating and optional review | `{ "rating": 5, "text": "Great read!" }` |
| `GET` | `/stats` | Return shelf counts and rating statistics | N/A |

There is no general `PATCH /books/{id}` endpoint and there are no review update or review delete endpoints in M1.

## Open Library Integration

The application calls the keyless, public Open Library API directly over HTTP from `app/openlibrary.py`. There is no account, key, or secret to configure. Two functions are exposed:

1. `search_book(title: str)`
   - `GET https://openlibrary.org/search.json`, requesting only the fields used.
   - Returns up to five matches in Open Library's own relevance order: title, author, first publication year, a preferred 13-digit ISBN, and a cover URL.

2. `get_book_details(isbn: str)`
   - `GET https://openlibrary.org/api/books?bibkeys=ISBN:<isbn>&jscmd=data`.
   - Returns the record for that ISBN, or `None` when the catalogue has none.

The Open Library response shape stays outside the core data model: the client converts catalogue JSON into `BookDetails` (`app/details.py`) and touches nothing else.

`app/lookup.py` chooses the backend and degrades in steps:

1. A network error, HTTP error status, or unparseable body raises `LookupUnavailable` — "the catalogue is down", as distinct from an empty result meaning "no such book".
2. `lookup` catches it and falls back to the seed. An empty live result falls back the same way.
3. If the seed has nothing either, `lookup` returns `None` and `POST /books` saves the typed title with `details_pending = 1`.

Adding a book therefore never fails because the catalogue is unavailable.

### Configuration

| Variable | Default | Purpose |
| :--- | :--- | :--- |
| `SHELF_LIFE_LOOKUP_BACKEND` | `openlibrary` | `openlibrary` for the live catalogue, `seed` to stay entirely offline |
| `SHELF_LIFE_OPENLIBRARY_TIMEOUT` | `5` | Seconds to wait for Open Library before falling back |

Set `SHELF_LIFE_LOOKUP_BACKEND=seed` to demo with no network at all.

An MCP server wrapping these same two functions remains a possible follow-up; the HTTP client is what the application calls today.

## Milestones

### M1: Data and CRUD Core

- SQLite schema for `Book` and `Review`.
- REST endpoints for books, shelves, reviews, health, and statistics.
- Offline `lookup(title)` backed by `seed/books.json`.
- Three-shelf browser interface.
- Automated tests for the current API and lookup behavior.

### M2: External Integration

- Done: `search_book` and `get_book_details` implemented in `app/openlibrary.py`.
- Done: the existing lookup interface connected to the live Open Library API, with no caller changed.
- Done: fallback behavior preserved when Open Library is unavailable.
- Done: mocked network tests; no test reaches the real catalogue.
- Remaining: run the required security scan.
- Remaining: add only the M2 extensions agreed by the team after scope review, and an MCP server over the same two functions if the demo calls for one.

## Technology Stack

- Python 3.11+
- FastAPI
- Pydantic 2.x
- SQLite through the standard-library `sqlite3` module
- HTML, CSS, vanilla JavaScript, and Jinja2
- pytest

## Development and Testing Rules

- Keep core models independent from external API response formats.
- Validate shelves as `reading`, `finished`, or `wishlist`.
- Validate ratings as integers from `1` to `5`.
- Keep the `lookup(title)` interface stable so the seed backend and the Open Library backend are interchangeable.
- A lookup failure must not prevent a book from being added; save it with `details_pending = 1`.
- Never access a real external API in automated tests; use seed data or mocks. `tests/conftest.py` enforces this: it pins the seed backend for every test and replaces the HTTP client factory with one that raises, so an accidental live call fails loudly. Tests that need the Open Library path use the `mock_openlibrary` fixture.
- Use parameterized SQL and never build SQL through string concatenation.
- Render user-supplied text with `textContent`, never `innerHTML`.
- Never commit credentials, API keys, `.env` files, local databases, virtual environments, or test caches.
- Do not add a dependency without explaining why it is required.
- Follow the existing router/service separation.
- Add or update tests for every behavior change.
- Do not claim that tests passed unless they were actually run.
- On this Windows setup, run pytest with a project-local temporary directory if the system temp directory denies access:

  ```powershell
  ..\.venv\Scripts\python.exe -m pytest --basetemp=.test-tmp
  ```

## Project Layout

```text
app/
  main.py             FastAPI entry point: /, /stats, /health
  db.py               SQLite schema and connection helpers
  models.py           Pydantic request and response models
  details.py          BookDetails: the value type both lookup backends return
  openlibrary.py      live Open Library HTTP client
  lookup.py           lookup(title): picks a backend, seed as the fallback
  routers/books.py    /books endpoints
  routers/reviews.py  /books/{id}/reviews endpoints
  services/stats.py   reading statistics
seed/books.json       seeded titles for the offline demo and outage fallback
templates/index.html  three-shelf interface
static/styles.css     interface styling
static/app.js         browser behavior and API calls
tests/                API, lookup, and Open Library tests
```
