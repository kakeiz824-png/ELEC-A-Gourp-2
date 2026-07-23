# CLAUDE.md - Shelf Life Project Guide

## Project Overview
**Shelf Life** is a personal reading tracker application that helps users organize their reading list across three primary shelves: `reading`, `finished`, and `wishlist`. It includes reviews, ratings, and automated book detail enrichment (author, cover image, publication year) by integrating with the **Open Library API** via Model Context Protocol (MCP).

---

## Pitch & Core Philosophy
> A personal reading tracker with automated book metadata enrichment powered by Open Library. Features a simple, robust data model with deep testing potential and room for UI/UX polish.

---

## Data Model Architecture

```
+------------------------------------+         +-----------------------+
|                Book                | 1     * |        Review         |
+------------------------------------+---------+-----------------------+
| id: String / UUID                  |         | id: String / UUID     |
| title: String                      |         | book_id: FK -> Book   |
| author: String                     |         | rating: Integer (1-5) |
| isbn: String                       |         | text: Text / String   |
| shelf: Enum(reading|finished|wish) |         | created_at: Timestamp |
| cover_url: String (optional)       |         +-----------------------+
| publish_year: Integer (optional)   |
| created_at: Timestamp              |
+------------------------------------+
```

> **Open question:** the code currently follows DESIGN.md instead — integer primary
> keys, a `year` column rather than `publish_year`, and an extra `details_pending`
> flag. Settle this before M2 and update whichever document is wrong.

---

## Requirements & Scope (MoSCoW)

### Must Have (Core Functionality)
- **Book & Shelf CRUD Operations**: Create, read, update, delete books and assign/move them between shelves (`reading`, `finished`, `wishlist`).
- **Open Library Lookup**: Auto-fill book details (author, cover, publication year) using title search or ISBN.
- **Review & Rating Core**: Basic CRUD for reviews and ratings attached to books.

### Should Have (Enhanced Experience)
- **Reading Statistics**: Summary metrics (total books read, average rating, books per shelf).
- **Cover Images Display**: Render book cover thumbnails dynamically from Open Library or stored URLs.

### Could Have (Future Extensions)
- **Book Recommendations**: Simple rule-based or similarity-based book suggestions.
- **Goodreads CSV Import**: Batch import existing libraries from Goodreads CSV exports.

---

## API Endpoint Specifications

| Method | Endpoint | Description | Query / Body Params |
| :--- | :--- | :--- | :--- |
| `GET` | `/books` | Retrieve books (filtered by shelf) | `?shelf=reading\|finished\|wishlist` |
| `POST` | `/books` | Add a book (triggers Open Library auto-lookup) | `{ "title": "...", "shelf": "wishlist" }` |
| `PATCH` | `/books/{id}/shelf` | Move a book to a different shelf | `{ "shelf": "finished" }` |
| `GET` | `/books/{id}` | Get detailed book info with reviews | — |
| `DELETE` | `/books/{id}` | Delete a book; its reviews cascade | — |
| `POST` | `/books/{id}/enrich` | Retry the lookup for a `details_pending` book | — |
| `GET` | `/books/{id}/reviews` | List the reviews on a book | — |
| `POST` | `/books/{id}/reviews` | Add a review and rating to a book | `{ "rating": 5, "text": "Great read!" }` |
| `GET` | `/stats` | Counts per shelf and average rating | — |

---

## MCP Server Tools (Open Library Integration)

The app connects to **Open Library** (Keyless / Public API) via an MCP server wrapping the following tools:

1. `search_book(title: str)`
   - Performs a title search on Open Library API.
   - Returns top matched results with `title`, `author_name`, `first_publish_year`, `cover_i`, `isbn`.

2. `get_book_details(isbn: str)`
   - Fetches precise metadata for a given ISBN.
   - Returns detailed record including description, author, publication date, and high-res cover image URL.

---

## Milestones

* **Milestone 1 (M1): Data & CRUD Core**
  * Database setup & schema migrations (`Book`, `Review`).
  * Basic REST endpoints for books, shelves, and reviews.
  * Test coverage for database models and core API routes.
  * `lookup(title)` backed by the seeded table in `seed/books.json`, so the
    add-by-title demo runs with no network.

* **Milestone 2 (M2): MCP Server & External Integration**
  * Implement keyless Open Library MCP wrapper server (`search_book`, `get_book_details`).
  * Connect `POST /books` flow to automatically query Open Library and auto-populate author, cover image, and publication year.
  * Implement frontend/UI polish & reading statistics.

---

## Technology stack

- Python 3.11+
- FastAPI
- Pydantic 2.x
- SQLite via the standard-library `sqlite3` module
- HTML, CSS, and vanilla JavaScript (Jinja2 templates in `templates/`, assets in `static/`)
- pytest

---

## Development & Testing Guidelines

* Keep data models clean and decoupled from external API responses.
* Enforce validation on shelf status values (`reading`, `finished`, `wishlist`) and ratings (`1` to `5`).
* Unit test external API wrappers with mock network responses.
* Maintain comprehensive API test coverage for all CRUD and endpoint edge cases.
* Keep the `lookup(title)` interface stable — the M1 seed and the M2 MCP client
  must be swappable without touching any router.
* A lookup failure must never fail the add: save the title with
  `details_pending = 1` instead of returning an error.
* Never access a real external API in automated tests; use the seed or mocks.
* Use parameterised SQL — never build a query by string concatenation.
* Render user-supplied text with `textContent`, never `innerHTML`.
* Never commit credentials, API keys, or `.env` files.
* Do not add a dependency without explaining why it is needed.
* Do not claim that tests passed unless they were actually executed.

---

## Layout

```
app/
  main.py            FastAPI entry point: /, /stats, /health
  db.py              SQLite schema and connection helpers
  models.py          Pydantic request/response models
  lookup.py          lookup(title): seeded at M1 -> MCP/Open Library at M2
  routers/books.py   /books endpoints
  routers/reviews.py /books/{id}/reviews endpoints
  services/stats.py  reading statistics
seed/books.json      seeded titles for M1 and the offline demo
templates/index.html three-shelf interface
static/              styles.css, app.js
tests/               test_books.py, test_lookup.py, test_reviews.py
```
