# Shelf Life — Design Document

## Overview

Shelf Life is a personal reading tracker. Readers organise books across three shelves —
**reading**, **finished**, and **wishlist** — and can leave a rating and review on any book.
The point of difference: you add a book by typing **only its title**, and the app fills in the
author, cover image, and publication year automatically by looking the title up on the
Open Library API. It is built for people who read enough that manual data entry (typing an
author and hunting for a cover) is the thing that makes them stop tracking their reading.

## Demo Contract

- **Intended audience:** A VSP student who reads several books a term and keeps losing track
  of which ones they have finished versus still want to read — and who will not maintain a
  tracker that makes them type an author, ISBN, and cover URL by hand for every book.

- **One-sentence problem:** Logging a book usually means typing all its metadata, and that
  friction is enough to make people abandon reading trackers within a week.

- **Magic moment:** *Given a book title typed into the "add" box, the system looks the title
  up on Open Library, auto-fills the author, cover, and year, and the book appears on the
  Reading shelf as a finished card — the user never types anything but the title.*

- **Exact demo input → expected output:**
  - **Input (typed on demo day):** `The Hobbit` in the add-book box, then press Add.
  - **Expected output:** A book card appears on the **Reading** shelf showing
    Title = `The Hobbit`, Author = `J. R. R. Tolkien`, Year = `1937`, ISBN = `9780261103344`,
    and a cover thumbnail. No other fields were typed.

- **Three screens / states you will show:**
  1. **Empty state** — Reading shelf with no books, just the add box and a hint.
  2. **Input / looking-up state** — user has typed `The Hobbit`, a spinner/"Looking up…" note
     shows while Open Library is queried.
  3. **Result state** — the fully-populated book card (cover + author + year) sitting on the
     Reading shelf.

- **If the external API is unavailable:** The book is **still created** using the title the
  user typed, with a placeholder cover and the note *"Couldn't fetch details — saved your
  title, tap retry later."* The book keeps a `details_pending` flag so it can be enriched
  later. In addition, a small set of seeded titles (including `The Hobbit`) is cached in the
  database so the **demo always works even with no network**.

- **Evidence the result is trustworthy:** An automated test feeds the literal demo input
  (`The Hobbit`) through the lookup and asserts `author == "J. R. R. Tolkien"` and that the
  returned cover URL is non-empty. Each auto-filled book also stores and displays its ISBN,
  which links back to the Open Library record as a visible source citation.

**Building it in stages.**
- **M1 (walking skeleton):** The full add-by-title → auto-filled card path works end-to-end,
  but the Open Library call is **replaced by a seeded lookup** (a small in-code table mapping
  a handful of titles, including `The Hobbit`, to author/year/cover/ISBN). The magic moment is
  demoable — mocked — the day M1 is due.
- **M2 (real):** Swap the seeded lookup for the live Open Library MCP tools
  (`search_book` / `get_book_details`), keeping the same interface so nothing else changes.

## Current Context

- **What problem does this solve?** Reading trackers fail because manual metadata entry is
  tedious; Shelf Life removes that friction by auto-filling everything from a title.
- **Who are the target users?** Individual readers (students, hobby readers) who want a
  lightweight private shelf system, not a social network.
- **What existing solutions exist and why are they insufficient?**
  - *Goodreads* — powerful but heavy, ad-driven, and social-first; overkill for private
    tracking and slow to add a book.
  - *A spreadsheet* — free and flexible but every field is manual, no covers, no lookup.
  - *Notes app* — zero structure, no shelves, ratings, or statistics.

## Requirements

### Functional Requirements
- [ ] Add a book by **title only**; author, cover, year, and ISBN are auto-filled via lookup.
- [ ] Organise books across three shelves: **reading**, **finished**, **wishlist**.
- [ ] Move a book between shelves.
- [ ] Full CRUD on books (create, list, view, update, delete).
- [ ] Leave a **rating (1–5)** and optional **review text** on a book; a book may have many reviews.
- [ ] List books filtered by shelf.
- [ ] Graceful fallback when the lookup API is unavailable (save title + `details_pending`).
- [ ] *(Should)* Reading statistics — counts per shelf, books finished, average rating.
- [ ] *(Should)* Display cover images.
- [ ] *(Could)* Recommendations; CSV import from Goodreads.

### Non-Functional Requirements
- **Performance:** A book lookup + create returns in < 2 s on a normal connection; list
  endpoints return in < 200 ms for a personal-scale library (hundreds of books, single user).
- **Security:** All inputs validated; parameterised SQL only; no secrets in code (Open Library
  is keyless, so there is no API key to leak); CORS restricted to the frontend origin.
- **Accessibility:** Cover images have alt text (book title + author); the add box and shelf
  controls are keyboard-navigable; colour is not the only signal for shelf membership.
- **Reliability:** The app never hard-fails on an external-API outage — it degrades to
  title-only records plus seeded samples.

## Design Decisions

### 1. Shelf as a field on Book, not a separate Shelf entity

**Decision:** Model the shelf as an enum column (`reading` | `finished` | `wishlist`) on the
`books` table rather than a separate `shelves` table with a join, because:
- There are exactly three fixed, well-known shelves — no user-created shelves in scope.
- It keeps the data model as simple as the handout's "steadiest option" note intends.
- Moving a book is a single-column `PATCH`, which maps cleanly to `PATCH /books/{id}/shelf`.

**Alternatives considered:**
- *Separate `shelves` table + FK:* Rejected — adds a join and migration surface for zero
  benefit while the shelf set is fixed.
- *Many-to-many (a book on multiple shelves):* Rejected — a book is in exactly one reading
  state at a time; multi-shelf contradicts the mental model.

### 2. Wrap Open Library (keyless) rather than Google Books

**Decision:** Use the **Open Library** API for title search and details because:
- It is **keyless** — no API key to provision, store, or accidentally commit (removes a whole
  class of security risk and matches the M1-before-keys timeline).
- It exposes both a search endpoint and stable cover URLs by ISBN, covering the Must
  requirements directly.

**Alternatives considered:**
- *Google Books API:* Rejected — richer data but requires an API key and quota management.
- *Hardcoding a book list:* Rejected — defeats the magic moment; only used as the M1 seed/mock.

### 3. Seeded/mock lookup at M1, live MCP tool at M2

**Decision:** Define one internal `lookup(title)` interface. At M1 it is backed by a seeded
table; at M2 it is backed by the MCP server's `search_book`. The rest of the app depends only
on the interface, so the M1→M2 swap touches one module.

## Technical Design

### System Architecture

```
[Frontend (index.html)] --> [API Layer (FastAPI)] --> [Database (SQLite)]
                                                  --> [Lookup interface]
                                                         M1: seeded table
                                                         M2: MCP server --> Open Library API
```

### Data Models

```python
# SQLite schema

books = """
    CREATE TABLE books (
        id              INTEGER PRIMARY KEY,
        title           TEXT NOT NULL,
        author          TEXT,
        isbn            TEXT,
        cover_url       TEXT,
        year            INTEGER,
        shelf           TEXT NOT NULL DEFAULT 'reading'
                        CHECK (shelf IN ('reading', 'finished', 'wishlist')),
        details_pending INTEGER NOT NULL DEFAULT 0,   -- 1 if lookup failed, enrich later
        created_at      TEXT DEFAULT (datetime('now'))
    )
"""

reviews = """
    CREATE TABLE reviews (
        id         INTEGER PRIMARY KEY,
        book_id    INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
        rating     INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
        text       TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    )
"""
# Relationship: one Book has many Reviews (1 --- *).
```

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /books | List books; optional `?shelf=reading\|finished\|wishlist` filter |
| POST | /books | Add a book by title; looks up author/cover/year (Open Library) and saves |
| GET | /books/{id} | Get one book (with its reviews) |
| PATCH | /books/{id}/shelf | Move a book to another shelf |
| DELETE | /books/{id} | Delete a book (cascades to its reviews) |
| POST | /books/{id}/reviews | Add a rating + review to a book |
| GET | /books/{id}/reviews | List reviews for a book |
| GET | /stats | *(Should)* Reading statistics: counts per shelf, avg rating |

**`POST /books` request/response sketch:**
```
Request:  { "title": "The Hobbit" }
Response: { "id": 1, "title": "The Hobbit", "author": "J. R. R. Tolkien",
            "year": 1937, "isbn": "9780261103344",
            "cover_url": "https://covers.openlibrary.org/b/isbn/9780261103344-M.jpg",
            "shelf": "reading", "details_pending": false }
```

### MCP Server Design

**External API:** Open Library (`https://openlibrary.org`, keyless).

**Tools to expose:**
1. `search_book(title: str)` — Search Open Library by title; returns a list of candidates,
   each `{ title, author, isbn, year, cover_url }`. Used by `POST /books` to auto-fill.
2. `get_book_details(isbn: str)` — Fetch full details for a specific ISBN; returns
   `{ title, author, isbn, year, cover_url, subjects }`. Used to enrich `details_pending` books.

**Transport:** STDIO (local) for development and the Session-5 integration.

### File Structure

```
shelf-life/
├── app/
│   ├── main.py          # FastAPI entry point
│   ├── db.py            # SQLite schema + connection helpers
│   ├── lookup.py        # lookup(title) interface: seeded (M1) -> MCP/Open Library (M2)
│   ├── routers/
│   │   ├── books.py     # /books, /books/{id}, /books/{id}/shelf
│   │   └── reviews.py   # /books/{id}/reviews
│   └── services/
│       └── stats.py     # reading statistics
├── mcp-server/
│   └── server.py        # MCP server wrapping Open Library
├── frontend/
│   └── index.html       # Three-shelf web interface
├── tests/
│   ├── test_books.py    # CRUD + shelf move
│   ├── test_lookup.py   # demo-input test: "The Hobbit" -> Tolkien + cover
│   └── test_reviews.py  # rating validation, cascade delete
├── seed/
│   └── books.json       # seeded titles (incl. The Hobbit) for M1 + offline demo
├── CLAUDE.md            # AI agent context
└── README.md            # Setup and usage docs
```

## Implementation Plan

### Phase 1: Core Application (Week 1) — M1 walking skeleton
- [ ] Set up project structure and CLAUDE.md
- [ ] Implement `books` + `reviews` schema and CRUD operations
- [ ] Build `/books`, `/books/{id}`, `/books/{id}/shelf`, review endpoints
- [ ] Implement `lookup(title)` backed by the **seeded** table (mock Open Library)
- [ ] Build the three-shelf frontend (empty → looking-up → result states)
- [ ] Write the demo-input test (`The Hobbit` → Tolkien) and CRUD tests

### Phase 2: MCP Integration (Week 2) — M2 real API
- [ ] Design and implement the MCP server (`search_book`, `get_book_details`)
- [ ] Swap `lookup(title)` from seeded table to the live Open Library MCP tool
- [ ] Add the API-unavailable fallback (title-only + `details_pending`)
- [ ] Generate and review the test suite with AI
- [ ] Run Semgrep security scan and fix findings

### Phase 3: Polish and Deploy (Week 3)
- [ ] Reading statistics + cover images (Should tier)
- [ ] Polish UI/UX (shelf transitions, alt text, keyboard nav)
- [ ] Deploy to a hosting platform
- [ ] Write documentation
- [ ] Prepare presentation

## Testing Strategy

### Unit Tests
- Each endpoint, happy path + error cases (unknown id, invalid shelf, rating out of 1–5).
- Database operations, including `ON DELETE CASCADE` from book to reviews.
- `lookup(title)`: the **demo-input test** asserting `The Hobbit` → author `J. R. R. Tolkien`
  and a non-empty cover URL.

### Integration Tests
- MCP server connected to the app: `POST /books {title}` results in an auto-filled record.
- Full user workflow: add by title → move shelf (reading → finished) → add review → delete.
- API-outage path: lookup failure yields a `details_pending` book, not a 500.

### Security Testing
- Run Semgrep on all code.
- Check for SQL injection (parameterised queries only), XSS in review text rendering,
  and hardcoded secrets.
- Validate all user inputs (title length, rating range, shelf enum).

## Security Considerations

- [ ] Input validation on all endpoints (title, rating 1–5, shelf enum, id existence)
- [ ] No hardcoded secrets — Open Library is keyless; any future keys via environment variables
- [ ] SQL parameterised queries (no string concatenation)
- [ ] CORS restricted to the frontend origin
- [ ] Escape/sanitise user-supplied review text before rendering (XSS)
- [ ] Rate limiting / timeout on outbound Open Library calls; cache results to reduce calls

## References

- [Shelf Life project brief](https://ubc-vsp26.github.io/assets/handouts/project-ideas.pdf)
- [Open Library API](https://openlibrary.org/developers/api)
- [Open Library Covers API](https://openlibrary.org/dev/docs/api/covers)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [MCP Server Quickstart](https://modelcontextprotocol.io/quickstart/server)
- [Semgrep Getting Started](https://semgrep.dev/docs/getting-started/)
