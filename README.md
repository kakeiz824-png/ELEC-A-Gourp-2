Shelf Life Project Guide

## Project Overview

**Shelf Life** is a personal reading tracker that organizes books across three shelves: `reading`, `finished`, and `wishlist`. It includes ratings, optional review text, reading statistics, and automated book-detail enrichment. In M1, enrichment uses the offline seed in `seed/books.json`; the Open Library MCP integration is planned for M2.

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

## Planned M2 MCP Tools

M1 does not contain an MCP server and does not make live Open Library requests. M2 will add a keyless Open Library MCP server exposing:

1. `search_book(title: str)`
   - Search Open Library by title.
   - Return matched title, authors, first publication year, cover identifier, and ISBN.

2. `get_book_details(isbn: str)`
   - Retrieve metadata for a selected ISBN.
   - Return normalized details such as description, author, publication date, and cover URL.

The MCP response shape must stay outside the core data model. The application should convert MCP results into the existing `BookDetails` format.

## Milestones

### M1: Data and CRUD Core

- SQLite schema for `Book` and `Review`.
- REST endpoints for books, shelves, reviews, health, and statistics.
- Offline `lookup(title)` backed by `seed/books.json`.
- Three-shelf browser interface.
- Automated tests for the current API and lookup behavior.

### M2: MCP Server and External Integration

- Implement `search_book` and `get_book_details`.
- Connect the existing lookup interface to Open Library.
- Preserve fallback behavior when Open Library is unavailable.
- Add mocked MCP/network tests.
- Run the required security scan.
- Add only the M2 extensions agreed by the team after scope review.

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
- Keep the `lookup(title)` interface stable so M1 seed lookup and the M2 MCP client are interchangeable.
- A lookup failure must not prevent a book from being added; save it with `details_pending = 1`.
- Never access a real external API in automated tests; use seed data or mocks.
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
  lookup.py           lookup(title): M1 seed -> M2 MCP/Open Library
  routers/books.py    /books endpoints
  routers/reviews.py  /books/{id}/reviews endpoints
  services/stats.py   reading statistics
seed/books.json       seeded titles for the M1 offline demo
templates/index.html  three-shelf interface
static/styles.css     interface styling
static/app.js         browser behavior and API calls
tests/                API and lookup tests
```
