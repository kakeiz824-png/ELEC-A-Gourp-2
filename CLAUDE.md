# CLAUDE.md - Shelf Life Development Guide

## 1. Project Overview

Shelf Life is a single-user personal reading tracker built with FastAPI, SQLite,
Jinja2, HTML, CSS, and vanilla JavaScript.

Users can:

- add a book by typing only its title;
- organize books across `reading`, `finished`, and `wishlist`;
- view author, ISBN, publication year, and cover information when available;
- move and delete books;
- add a rating from 1 to 5 and optional review text; and
- view shelf counts, review totals, and average ratings.

### Current state

The M1 CRUD application is working. The application currently searches the keyless
Open Library API directly through `app/openlibrary.py`. If the live service fails or
returns no match, it falls back to `seed/books.json`. If neither source has a match,
the typed title is still stored with `details_pending = true`.

The course-required MCP server has **not** been implemented yet. It is an M2 task.
Do not describe the current direct HTTP client as an MCP server.

### Current milestone priorities

1. Keep the M1 application stable and tested.
2. Implement the M2 Open Library MCP server and connect it through the existing
   lookup boundary.
3. Add mocked MCP tests and run the required security scan.
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
SQLite database          lookup(title)
                              |
                    +---------+----------+
                    |                    |
            Open Library HTTP      seed/books.json
                    |
          future M2 MCP boundary
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
| `isbn` | Text or null | Filled by lookup when available |
| `cover_url` | Text or null | Filled by lookup when available |
| `year` | Integer or null | First publication year when available |
| `shelf` | Text | `reading`, `finished`, or `wishlist` |
| `details_pending` | Boolean/integer | True when enrichment is incomplete |
| `created_at` | Timestamp text | Assigned by SQLite |

#### Review

| Field | Type | Rules |
|---|---|---|
| `id` | Integer | SQLite primary key |
| `book_id` | Integer | Foreign key to `Book` |
| `rating` | Integer | Required, 1-5 |
| `text` | Text or null | Optional, maximum 2,000 characters |
| `created_at` | Timestamp text | Assigned by SQLite |

One Book can have many Reviews. Deleting a Book cascade-deletes its Reviews.

### Current API

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/` | Render the three-shelf interface |
| `GET` | `/health` | Return application health |
| `GET` | `/books` | List books; optionally filter with `?shelf=` |
| `POST` | `/books` | Add a book and attempt metadata lookup |
| `GET` | `/books/{id}` | Return one book with its reviews |
| `PATCH` | `/books/{id}/shelf` | Move a book to another shelf |
| `POST` | `/books/{id}/enrich` | Retry metadata lookup |
| `DELETE` | `/books/{id}` | Delete a book and its reviews |
| `GET` | `/books/{id}/reviews` | List reviews for a book |
| `POST` | `/books/{id}/reviews` | Add a rating and optional review |
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
  lookup.py            Selects live/seed lookup and handles fallback
  openlibrary.py       Direct Open Library HTTP client
  routers/
    books.py           Book and shelf endpoints
    reviews.py         Rating and review endpoints
  services/
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
  test_books.py
  test_lookup.py
  test_openlibrary.py
  test_reviews.py
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

### Optional configuration

| Environment variable | Default | Purpose |
|---|---|---|
| `SHELF_LIFE_DB` | `shelf_life.db` | SQLite database path |
| `SHELF_LIFE_ORIGINS` | localhost origins | Comma-separated CORS allowlist |
| `SHELF_LIFE_LOOKUP_BACKEND` | `openlibrary` | Use `openlibrary` or offline `seed` |
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
- Preserve the stable `lookup(title)` interface when adding the MCP client.
- Validate shelf values as `reading`, `finished`, or `wishlist`.
- Validate ratings as integers from 1 to 5.
- Treat metadata lookup as enrichment, not a requirement for book creation.
- If all lookup sources fail, save the title with `details_pending = true`.
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
3. Preserve seed fallback and `details_pending` behavior.
4. Mock every external response in tests.
5. Test empty results, missing fields, timeouts, bad status codes, and malformed data.

### Add the M2 MCP server

1. Expose `search_book(title)` and `get_book_details(isbn)` as MCP tools.
2. Reuse the existing normalization and failure-handling rules.
3. Connect the MCP client through `lookup(title)` rather than directly from a router.
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
