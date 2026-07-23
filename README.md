# Shelf Life

Shelf Life is a FastAPI personal reading tracker. Books sit on one of three
shelves — **reading**, **finished**, **wishlist** — and can carry ratings and
reviews. You add a book by typing **only its title**: the author, cover, year,
and ISBN are filled in for you.

This repository contains the M1 walking skeleton. The add-by-title path works
end to end, but the lookup is backed by a seeded table
(`seed/books.json`) rather than the live Open Library API, so the demo runs with
no network. M2 swaps that one module for the Open Library MCP server without
changing any caller.

## Current functionality

- `GET /` renders the three-shelf interface.
- `POST /books` adds a book from its title and auto-fills author, cover, year,
  and ISBN. A failed lookup still saves the book, flagged `details_pending`.
- `GET /books` lists books, optionally filtered by `?shelf=`.
- `GET /books/{id}` returns one book with its reviews.
- `PATCH /books/{id}/shelf` moves a book between shelves.
- `POST /books/{id}/enrich` retries the lookup for a pending book.
- `DELETE /books/{id}` deletes a book; its reviews cascade.
- `POST /books/{id}/reviews` and `GET /books/{id}/reviews` handle ratings (1–5)
  and optional review text.
- `GET /stats` returns counts per shelf, review count, and average rating.
- `GET /health` returns the application status as JSON.

The Open Library MCP server, the live lookup, and deployment come in later
milestones.

## Requirements

- Python 3.11 or newer
- Git

## Run locally on Windows

Create and activate a virtual environment:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Install the dependencies:

```powershell
python -m pip install -r requirements.txt
```

Start the development server:

```powershell
python -m uvicorn app.main:app --reload
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000) in a browser and type
`The Hobbit` into the add box. Interactive API docs are at
[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs), and the health
endpoint at [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health).

## Configuration

Both settings are optional and read from the environment.

| Variable | Default | Purpose |
|---|---|---|
| `SHELF_LIFE_DB` | `shelf_life.db` in the repository root | SQLite database file |
| `SHELF_LIFE_ORIGINS` | `http://127.0.0.1:8000,http://localhost:8000` | Comma-separated CORS allowlist |

The database file is created on startup and is git-ignored.

## Run the tests

```powershell
python -m pytest
```

The suite covers book CRUD, shelf moves, review validation, the delete cascade,
statistics, the lookup-outage fallback, and the demo-input test asserting that
`The Hobbit` resolves to J. R. R. Tolkien with a non-empty cover URL.

## Seeded titles

`seed/books.json` holds the titles the M1 lookup can resolve. Lookup ignores
case, surrounding space, and punctuation, and will match a partial title, so
`the hobbit` and `sapiens` both work. Add an entry there to make another title
demoable; cover URLs are derived from the ISBN.

## Team workflow

New to Git or GitHub? Read [GIT_GUIDE.md](GIT_GUIDE.md) first — it walks
through cloning, branching, committing, pushing, opening a pull request, and
fixing the usual mistakes, step by step.

After the initial scaffold is on `main`, create a branch for every change:

```powershell
git pull
git checkout -b feature/short-description
```

Commit small, working changes and open a pull request for a teammate to
review. Do not commit directly to `main` after the initial scaffold.

## Milestones

- **M1 Foundation:** working skeleton, design document, AI instructions, and
  Book/Review CRUD backed by a database with a seeded lookup.
- **M2 Integration:** Open Library MCP server, live lookup, tests, and security
  scan.
- **M3 Ship It:** deployed application, completed README, and reflection.
