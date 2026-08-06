# CLAUDE.md - Shelf Life Development Guide

## 1. Project Overview

Shelf Life is a single-user personal reading tracker built with FastAPI, SQLite,
Jinja2, HTML, CSS, and vanilla JavaScript.

Users can:

- search by book title or by author name, page through the ISBN-bearing matches, and
  select one to add;
- organize books across `reading`, `finished`, and `wishlist`;
- view author, ISBN, publication year, and cover information when available;
- move and delete books;
- add a rating from 1 to 5 and optional review text; and
- view shelf counts, review totals, and average ratings.

### Current state

The M1 CRUD application is working. The default lookup backend calls the
`search_book`, `search_by_author`, and `get_book_details` MCP tools through
`app/mcp_client.py`. The tools use the keyless Open Library client. If MCP, the live
service, or the match is unavailable, the application falls back to `seed/books.json`.
A new book is stored only when the catalogue supplies an ISBN; otherwise `POST /books`
returns 404 without creating a row. The browser first uses
`GET /books/search?title=...` or `?author=...`; this search has no database side
effects. It then passes the selected candidate ISBN to `POST /books`.

The search box is paired with a Title/Author selector, so the server is told which
catalogue index to query and never infers it. Inferring it was tried and removed: no
rule tells "Harry Potter" the series from Harry Potter the legal historian, or "Dune"
the novel from Linda Dune, because in each pair both readings are real. See DESIGN.md
section 7.6.

Two indexes are needed because Open Library's title index answers an author's name
with books written about them: a title search for "George Orwell" returns his
biographies and a SparkNotes guide, never Nineteen Eighty-Four.

Results are paged, ten to a page, rather than capped at five, so a search for Harry
Potter can show all seven novels. `POST /books` confirms the submitted ISBN by
resolving it through `get_book_details` rather than by re-running the search, because
the chosen candidate may have come from page seven and catalogue relevance order
shifts between requests.

All three course-required M2 MCP catalogue tools are implemented in
`mcp_server/server.py` and reuse the existing normalized Open Library client. The
FastAPI application calls the same tools through FastMCP's in-memory transport. The
direct `openlibrary` backend is diagnostic compatibility, not the default path.

### Current milestone priorities

1. Keep the M1 application stable and tested.
2. Complete the M2 Open Library MCP tools and connect them through the existing
   lookup boundary.
3. Extend the mocked MCP tests and run the required security scan.
4. Add optional features only after the required M2 work is complete.

### Out of scope for the current milestone

- User accounts, friendships, chatrooms, and social permissions.
- AI-assisted conversational book discovery.
- Collaborative recommendations based on user behavior.
- Implementing all future roadmap ideas during M2.

These features require additional product decisions, data models, authentication,
authorization, privacy, moderation, or evaluation work.

## 2. Architecture

### Request flow

```text
Browser interface
      |
      v
FastAPI routes and Pydantic validation
      |                         |
      v                         v
SQLite database          services/search.py
                         (one paged search)
                              |
                              v
                   lookup: search_book / search_author
                              |     details_for_isbn
                    +---------+----------+
                    |                    |
             MCP client adapter      seed/books.json
                    |
   search_book / search_by_author / get_book_details
                    |
            Open Library HTTP

MCP client / Inspector
      |
      v
FastMCP STDIO server
      |
      v
Open Library HTTP
```

Routes must not depend on raw Open Library responses. External data is normalized
into the internal `BookDetails` shape before it reaches the routers or database.

### Data model

#### Book

| Field | Type | Rules |
|---|---|---|
| `id` | Integer | SQLite primary key |
| `title` | Text | Required, trimmed, 1-300 characters |
| `author` | Text or null | Filled by lookup when available |
| `isbn` | Text or null | Required for new books; null remains possible only on legacy rows |
| `cover_url` | Text or null | Filled by lookup when available |
| `year` | Integer or null | First publication year when available |
| `shelf` | Text | `reading`, `finished`, or `wishlist` |
| `details_pending` | Boolean/integer | True when enrichment is incomplete |
| `identity_key` | Text | Internal normalized ISBN; unique across tracked books |
| `created_at` | Timestamp text | Assigned by SQLite |

#### Review

| Field | Type | Rules |
|---|---|---|
| `id` | Integer | SQLite primary key |
| `book_id` | Integer | Foreign key to `Book` |
| `rating` | Integer | Required, 1-5 |
| `text` | Text or null | Optional, maximum 2,000 characters |
| `created_at` | Timestamp text | Assigned by SQLite |

Because the current application has one user, one Book has at most one Review.
Submitting another rating or review updates that record. Deleting a Book
cascade-deletes its Review.

### Current API

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/` | Render the three-shelf interface |
| `GET` | `/health` | Return application health |
| `GET` | `/books` | List books; optionally filter with `?shelf=` |
| `GET` | `/books/search` | Return one page of distinct ISBN-bearing candidates without storing them; takes exactly one of `?title=` or `?author=`, plus `?page=` and `?per_page=` |
| `POST` | `/books` | Add the selected ISBN; return 404 without an ISBN or 409 if it already exists |
| `GET` | `/books/{id}` | Return one book with its reviews |
| `PATCH` | `/books/{id}/shelf` | Move a book to another shelf |
| `POST` | `/books/{id}/enrich` | Retry metadata lookup |
| `DELETE` | `/books/{id}` | Delete a book and its reviews |
| `GET` | `/books/{id}/reviews` | List reviews for a book |
| `POST` | `/books/{id}/reviews` | Create or update the personal rating and review |
| `GET` | `/stats` | Return shelf and rating statistics |

There is no general book-update endpoint and no update/delete endpoint for an
individual review. Do not assume these endpoints exist.

### Project layout

```text
app/
  main.py              FastAPI entry point and page/health/stats routes
  db.py                SQLite schema and connection helpers
  models.py            Pydantic request and response models
  details.py           Normalized BookDetails value type
  lookup.py            Selects MCP/direct/seed lookup and handles fallback
  mcp_client.py        Converts MCP results into BookDetails
  openlibrary.py       Direct Open Library HTTP client
  routers/
    books.py           Book and shelf endpoints
    reviews.py         Rating and review endpoints
  services/
    books.py           Duplicate-safe book creation
    reviews.py         Single-user review upsert
    search.py          Pages one catalogue search into selectable candidates
    stats.py           Reading statistics
seed/
  books.json           Offline catalogue and network fallback
templates/
  index.html           Three-shelf browser interface
static/
  app.js               Browser behavior and API requests
  styles.css           Interface styling
tests/
  conftest.py
  test_author_search.py
  test_books.py
  test_lookup.py
  test_mcp_client.py
  test_mcp_server.py
  test_openlibrary.py
  test_reviews.py
  test_search_paging.py
mcp_server/
  __init__.py
  server.py
```

## 3. How to Run

Run commands from the repository root.

### Create the virtual environment

```powershell
python -m venv .venv
```

### Install dependencies

Use the virtual environment directly. PowerShell script activation is not required.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### Start the application

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Open:

- Web interface: `http://127.0.0.1:8000`
- API documentation: `http://127.0.0.1:8000/docs`
- Health endpoint: `http://127.0.0.1:8000/health`

### Run tests

```powershell
.\.venv\Scripts\python.exe -m pytest --basetemp=.test-tmp
```

The project-local `--basetemp` directory avoids the Windows system temporary-folder
permission error previously encountered by the team.

Do not claim that tests pass unless the current code has actually been tested.

### Start the Studio 5 MCP server

MCP clients launch the server as a STDIO subprocess:

```powershell
.\.venv\Scripts\python.exe -m mcp_server.server
```

The terminal waits silently for an MCP client; this command does not open a web
page. The server exposes `search_book`, `search_by_author`, and `get_book_details`.

### Optional configuration

| Environment variable | Default | Purpose |
|---|---|---|
| `SHELF_LIFE_DB` | `shelf_life.db` | SQLite database path |
| `SHELF_LIFE_ORIGINS` | localhost origins | Comma-separated CORS allowlist |
| `SHELF_LIFE_LOOKUP_BACKEND` | `mcp` | Use `mcp`, diagnostic `openlibrary`, or offline `seed` |
| `SHELF_LIFE_OPENLIBRARY_TIMEOUT` | `5` | Open Library timeout in seconds |

Open Library is keyless. Never add or request an API key for the current integration.

## 4. Code Conventions

- Use Python type hints for public functions.
- Use Pydantic models for request and response validation.
- Keep route handlers small; move reusable logic into focused modules or services.
- Keep database operations in `db.py` or the existing database helper layer.
- Use parameterized SQL. Never concatenate user input into SQL.
- Keep raw external API formats inside `openlibrary.py`.
- Convert external records into `BookDetails` before returning them to the core app.
- Preserve the stable `lookup` interface when adding the MCP client.
- Search an author's name with Open Library's `author=` index, never its `title=`
  index, which matches books written *about* the author.
- Require the caller to say which index to search. Do not infer it from the query; see
  DESIGN.md section 7.6 for the two ways that failed.
- Keep paging, ISBN de-duplication, and candidate assembly in `services/search.py`.
- Confirm a submitted ISBN with `details_for_isbn`, never by re-running a search.
- Validate shelf values as `reading`, `finished`, or `wishlist`.
- Validate ratings as integers from 1 to 5.
- Require lookup to supply an ISBN before creating a new book.
- Keep one tracked row per normalized ISBN. Duplicate adds return 409 and never
  move the existing book between shelves.
- Allow books with the same title when their ISBNs are different.
- Keep one personal review per book. A later submission updates the existing review.
- If all lookup sources fail or return no ISBN, reject the add without storing a row.
- Automated tests must not contact the real Open Library service; use mocks or seed data.
- Render user-provided text with `textContent`, not `innerHTML`.
- Do not commit API keys, `.env` files, virtual environments, local databases,
  caches, or test temporary directories.
- Add or update tests for every behavior change.
- Do not add a dependency without explaining why it is necessary.
- Keep documentation synchronized with the implemented code.

## 5. Common Tasks

### Add or change an API endpoint

1. Confirm that the endpoint is in `DESIGN.md`.
2. Add or update the relevant Pydantic model in `app/models.py`.
3. Implement the route in the appropriate router or service.
4. Use existing database helpers and error-response patterns.
5. Add success, validation, and not-found tests.
6. Update `DESIGN.md`, `README.md`, and this file if the public contract changed.

### Change the database schema

1. Update the schema in `app/db.py`.
2. Preserve foreign-key and validation constraints.
3. Consider how an existing local database will be handled.
4. Update Pydantic models and queries.
5. Add tests for the new field, relationship, or constraint.
6. Update the data-model sections in `DESIGN.md` and this file.

### Change Open Library lookup behavior

1. Keep HTTP-specific parsing and errors inside `app/openlibrary.py`.
2. Normalize results into `BookDetails`.
3. Preserve seed fallback and reject results that do not supply an ISBN.
4. Mock every external response in tests.
5. Test empty results, missing fields, timeouts, bad status codes, and malformed data.

### Add the M2 MCP server

1. Keep the tested `search_book`, `search_by_author`, and `get_book_details` tools
   stable.
2. Reuse the existing normalization and failure-handling rules.
3. Keep the MCP client connected through the `lookup` module, never directly from a
   router.
4. Preserve the offline seed fallback.
5. Add isolated mocked MCP tests.
6. Run the full test suite and the required security scan.
7. Update the architecture and running instructions only after the integration works.

### Change the browser interface

1. Keep HTML in `templates/index.html`, styles in `static/styles.css`, and behavior in
   `static/app.js`.
2. Preserve keyboard usability and meaningful image alternative text.
3. Render all user-provided content safely.
4. Manually verify adding, reviewing, moving, refreshing, and deleting a book.

### Before committing work

1. Review the changed files and remove unrelated edits.
2. Run the relevant tests, then the full test suite when practical.
3. Update documentation when behavior or structure changed.
4. Commit on a feature branch with a message explaining what changed and why.
5. Push the branch and open a pull request for teammate review.
