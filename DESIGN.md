# Shelf Life - Design Document

## 1. Overview

Shelf Life is a personal reading tracker. Readers organize books across three shelves:
`reading`, `finished`, and `wishlist`. They can add ratings and optional review text,
view reading statistics, and move books as their reading status changes.

The main interaction is intentionally simple: the user types only a title, and the
application attempts to fill in the author, ISBN, cover URL, and publication year.
M1 uses an offline catalogue in `seed/books.json`; M2 will replace that lookup backend
with keyless Open Library tools exposed through an MCP server.

## 2. Demo Contract

- **Audience:** students and hobby readers who want a lightweight way to track books.
- **Problem:** manually entering every author, ISBN, year, and cover makes reading
  trackers tedious to maintain.
- **Magic moment:** the user types `The Hobbit`, presses **Add book**, and a complete
  card appears with J. R. R. Tolkien, 1937, ISBN `9780261103344`, and a cover.
- **Exact demo input:** title = `The Hobbit`, shelf = `reading`.
- **Expected output:** one populated card on the Reading shelf.
- **Additional demo actions:** add a rating and review, move the book to Finished,
  refresh the page, and confirm the data persists.
- **Failure behavior:** if lookup returns no match or raises an error, the title is
  still saved with `details_pending = true`; the user can retry enrichment later.
- **M1 reliability:** the demo title is stored in `seed/books.json`, so the demo does
  not depend on network access.
- **Evidence:** automated tests verify the lookup result, CRUD behavior, validation,
  statistics, persistence behavior, and review cascade deletion.

## 3. Product Context

### Current M1 audience

M1 is a single-user personal tracker. It does not include authentication, friends,
public profiles, or chat.

### Future direction

The team may extend Shelf Life into a discovery and social-reading application.
Those features are recorded in the future roadmap, but they are not all commitments
for M2.

### Existing alternatives

- **Goodreads:** feature-rich and social-first, but heavier than a private tracker.
- **Spreadsheets:** flexible, but metadata and covers require manual work.
- **Notes applications:** easy to start, but lack shelves, validation, and statistics.

## 4. User Stories

### M1 user stories

1. As a reader, I want to add a book by title so that I do not enter all metadata.
2. As a reader, I want to choose Reading, Finished, or Wishlist when adding a book.
3. As a reader, I want to move a book between shelves as my reading status changes.
4. As a reader, I want to see a book's author, ISBN, year, and cover when available.
5. As a reader, I want to rate a book from one to five.
6. As a reader, I want to add optional review text.
7. As a reader, I want to delete a book I no longer want to track.
8. As a reader, I want my reviews removed automatically when their book is deleted.
9. As a reader, I want to filter books by shelf.
10. As a reader, I want to see totals, shelf counts, review count, and average rating.
11. As a reader, I want an unmatched title to be saved so that lookup failure does
    not lose my input.
12. As a reader, I want to retry enrichment for a book whose details are pending.

### Future user stories

1. As a reader, I want three related-book suggestions after selecting a book.
2. As a reader, I want to browse books by fiction and nonfiction categories.
3. As a reader, I want to search an author and view their books and biography.
4. As a member, I want an account, friends, and chatrooms for sharing books.
5. As a reader, I want to describe a book or my interests to an AI discovery assistant.
6. As a reader, I want goals, points, and achievement tiers for reading challenges.
7. As a member, I want to create shared booklists that others can discuss and rate.
8. As a member, I want a profile with public, friends-only, and private visibility.

## 5. Requirements and Scope

### Must Have - M1 core

- [x] Add a book using a title and shelf.
- [x] Attempt to fill author, ISBN, cover URL, and publication year.
- [x] Organize books across `reading`, `finished`, and `wishlist`.
- [x] List all books and filter them by shelf.
- [x] View one book together with its reviews.
- [x] Move a book to another shelf.
- [x] Delete a book and cascade-delete its reviews.
- [x] Create and list ratings with optional review text.
- [x] Validate shelf values, title length, and rating range.
- [x] Save unmatched titles with `details_pending`.
- [x] Retry enrichment for a pending book.

### Should Have - implemented in M1

- [x] Display cover images with a placeholder fallback.
- [x] Show book totals, shelf counts, review count, and average rating.
- [x] Provide a three-column browser interface.
- [x] Provide a health endpoint and interactive FastAPI documentation.

### Must Have - M2 integration

- [ ] Implement an MCP server that wraps the keyless Open Library API.
- [ ] Expose `search_book(title)` and `get_book_details(isbn)` tools.
- [ ] Connect the existing lookup interface to the MCP tools.
- [ ] Preserve title-only fallback behavior during network failures.
- [ ] Test the MCP tools using mocks rather than live network calls.
- [ ] Run the required security scan and review the findings.

### Could Have - future roadmap

- [ ] Related-book recommendation page.
- [ ] Fiction and nonfiction category browsing.
- [ ] Author search, work catalogue, and biography.
- [ ] Accounts, friends, and chatrooms.
- [ ] AI-assisted book search and recommendations.
- [ ] Reading challenges, points, and achievement tiers.
- [ ] Shared booklists with comments and ratings.
- [ ] User profiles and privacy controls.

The team will choose a small subset of these roadmap items only after the M2 MCP,
testing, and security requirements are planned. Social features require authentication,
authorization, privacy, abuse prevention, and moderation design.

## 6. Non-Functional Requirements

- **Reliability:** lookup failure must not prevent a book from being stored.
- **Performance:** list and local CRUD operations should feel immediate for a
  personal-scale library of hundreds of books.
- **Security:** validate inputs, use parameterized SQL, restrict CORS, and never commit
  credentials or environment files.
- **Privacy:** M1 stores local single-user data. Future accounts must define ownership
  and public, friends-only, and private visibility.
- **Accessibility:** controls must be keyboard usable; covers need meaningful alt text;
  color must not be the only status indicator.
- **Testability:** automated tests must not require the real Open Library service.
- **Maintainability:** external response formats must be converted at the lookup boundary,
  not leaked into routers or core models.

## 7. Design Decisions

### 7.1 Shelf is a field on Book

M1 has exactly three fixed shelves, so `shelf` is a validated field on `books`.
Moving a book requires a single update and no join table.

If future shared or custom booklists are implemented, they will be modeled separately
from the three reading-status shelves.

### 7.2 Seeded lookup in M1, Open Library MCP in M2

The application depends on one internal `lookup(title)` interface. M1 implements it
with `seed/books.json`. M2 will replace the backend with an MCP client while keeping
the router contract stable.

### 7.3 Failure-safe creation

Lookup is enrichment, not a prerequisite for storing a book. If enrichment fails,
`POST /books` saves the typed title and sets `details_pending = 1`.

### 7.4 SQLite for the M1 walking skeleton

SQLite provides persistence, foreign keys, checks, and simple local setup. Each request
receives its own connection, foreign keys are enabled, and SQL parameters are used.

### 7.5 Recommendations must match available evidence

Early recommendations can use the same author or Open Library subjects. The product
must not label these as "people who liked this also liked" until real user-interaction
data exists.

## 8. System Architecture

```text
[Browser: HTML/CSS/JavaScript]
              |
              v
[FastAPI routes and validation]
       |                 |
       v                 v
[SQLite database]   [lookup(title) boundary]
                          |
                  +-------+--------+
                  |                |
             M1 seed JSON     M2 MCP client
                                   |
                                   v
                           [Open Library API]
```

## 9. Data Model

### Book

| Field | Type | Rules |
|---|---|---|
| `id` | Integer | Primary key |
| `title` | Text | Required, 1-300 characters after trimming |
| `author` | Text or null | Filled by lookup when available |
| `isbn` | Text or null | Filled by lookup when available |
| `cover_url` | Text or null | Filled by lookup when available |
| `year` | Integer or null | First publication year when available |
| `shelf` | Text | `reading`, `finished`, or `wishlist` |
| `details_pending` | Integer/Boolean | True when details still need enrichment |
| `created_at` | Text timestamp | Assigned by SQLite |

### Review

| Field | Type | Rules |
|---|---|---|
| `id` | Integer | Primary key |
| `book_id` | Integer | Foreign key to Book, cascade on delete |
| `rating` | Integer | Required, 1-5 |
| `text` | Text or null | Optional, maximum 2,000 characters |
| `created_at` | Text timestamp | Assigned by SQLite |

### Relationship

One Book can have many Reviews. A Review belongs to exactly one Book.

## 10. Current API

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/` | Render the three-shelf interface |
| `GET` | `/health` | Return application health |
| `GET` | `/books` | List books; optionally filter with `?shelf=` |
| `POST` | `/books` | Add a book and attempt lookup |
| `GET` | `/books/{id}` | Return one book with its reviews |
| `PATCH` | `/books/{id}/shelf` | Move a book to another shelf |
| `POST` | `/books/{id}/enrich` | Retry lookup for a book |
| `DELETE` | `/books/{id}` | Delete a book and its reviews |
| `GET` | `/books/{id}/reviews` | List reviews for a book |
| `POST` | `/books/{id}/reviews` | Add a rating and optional review |
| `GET` | `/stats` | Return counts and average rating |

M1 does not provide a general `PATCH /books/{id}` endpoint or update/delete endpoints
for individual reviews.

### Example add request

```json
{
  "title": "The Hobbit",
  "shelf": "reading"
}
```

### Example successful response

```json
{
  "id": 1,
  "title": "The Hobbit",
  "author": "J. R. R. Tolkien",
  "isbn": "9780261103344",
  "cover_url": "https://covers.openlibrary.org/b/isbn/9780261103344-M.jpg",
  "year": 1937,
  "shelf": "reading",
  "details_pending": false,
  "created_at": "2026-07-27 00:00:00"
}
```

## 11. Planned M2 MCP Design

### External service

Open Library is keyless and provides title search, edition data, author data, subjects,
and cover identifiers.

### MCP tools

1. `search_book(title: str)`
   - Return normalized candidate summaries.
   - Validate that the title is non-empty and bounded in length.
   - Apply request timeout and safe error handling.

2. `get_book_details(isbn: str)`
   - Return normalized details for a selected ISBN.
   - Validate ISBN input.
   - Include subjects required for category and related-book features when available.

### Integration boundary

MCP responses will be converted into the existing `BookDetails` shape. Routers will
continue to call `lookup(title)` and will not depend on raw Open Library JSON.

### Transport

Use STDIO for local development unless the course integration instructions require
another transport.

## 12. Actual M1 File Structure

```text
app/
  __init__.py
  db.py
  lookup.py
  main.py
  models.py
  routers/
    __init__.py
    books.py
    reviews.py
  services/
    __init__.py
    stats.py
seed/
  books.json
static/
  app.js
  styles.css
templates/
  index.html
tests/
  conftest.py
  test_books.py
  test_lookup.py
  test_reviews.py
CLAUDE.md
DESIGN.md
GIT_GUIDE.md
README.md
requirements.txt
```

The `mcp-server/` directory does not exist in M1. It will be added during M2.

## 13. Implementation Plan

### Phase 1 - M1 walking skeleton

- [x] Create project structure and AI context document.
- [x] Create Book and Review database tables.
- [x] Implement book creation, listing, detail, shelf move, enrichment retry, and delete.
- [x] Implement review creation and listing.
- [x] Implement seeded title lookup.
- [x] Implement the three-shelf interface.
- [x] Implement statistics and cover display.
- [x] Add automated tests.
- [x] Manually demonstrate add, review, shelf move, refresh persistence, and delete.

### Phase 2 - M2 MCP integration

- [ ] Define normalized MCP tool schemas.
- [ ] Implement `search_book`.
- [ ] Implement `get_book_details`.
- [ ] Add timeouts and safe error mapping.
- [ ] Connect the MCP client through the existing lookup boundary.
- [ ] Mock all external calls in automated tests.
- [ ] Run the full test suite.
- [ ] Run Semgrep and review findings.

### Phase 3 - selected extension and deployment work

- [ ] Select a realistically sized subset from the eight-item future roadmap.
- [ ] Add data models and authorization rules before building social features.
- [ ] Complete accessibility and interface polish.
- [ ] Deploy the application.
- [ ] Complete README, reflection, and presentation.

## 14. Testing Strategy

### Current automated coverage

- Book creation, listing, filtering, detail, shelf movement, enrichment, and deletion.
- Title and shelf validation.
- Review creation, listing, rating validation, and cascade deletion.
- Statistics before and after data is added.
- Seed lookup normalization, partial matching, and no-match behavior.
- Lookup exception fallback.
- Database connections used safely across FastAPI worker threads.

The suite was locally verified with:

```powershell
..\.venv\Scripts\python.exe -m pytest --basetemp=.test-tmp
```

Result: **38 passed, 1 deprecation warning**.

### M2 test requirements

- Unit-test each MCP tool with mocked Open Library responses.
- Test missing fields, empty results, invalid ISBNs, timeouts, and upstream errors.
- Confirm external failures still create a `details_pending` book.
- Never call the real Open Library API from the automated test suite.

## 15. Security Considerations

### Implemented in M1

- [x] Pydantic validation for title, shelf, rating, and review length.
- [x] SQLite checks for shelf and rating values.
- [x] Parameterized SQL.
- [x] Foreign-key cascade behavior.
- [x] CORS allowlist controlled by `SHELF_LIFE_ORIGINS`.
- [x] Browser rendering of user content through `textContent`.
- [x] No required API key for the M1 lookup.

### Required for M2

- [ ] Apply outbound request timeouts.
- [ ] Handle malformed or incomplete Open Library responses.
- [ ] Avoid logging sensitive user-provided content unnecessarily.
- [ ] Run Semgrep and manually review its findings.

### Required before social features

- [ ] Secure password storage or trusted identity-provider integration.
- [ ] Authorization checks on every private resource.
- [ ] Ownership rules for profiles, chatrooms, reviews, and shared lists.
- [ ] Privacy controls and safe defaults.
- [ ] Abuse reporting, moderation, blocking, and rate limiting.
- [ ] Protection against spam and unauthorized data exposure.

## 16. Future Roadmap Notes

- **Recommendation page:** begin with author and subject similarity. Collaborative
  recommendations require enough interaction data.
- **Categories:** derive normalized categories from Open Library subjects rather than
  storing an uncontrolled free-text category.
- **Author library:** use Open Library author identifiers to avoid confusing authors
  who share a name.
- **AI discovery:** define provider, cost limits, prompt-injection boundaries, and
  privacy rules before implementation.
- **Reading rewards:** use fixed achievement thresholds first; percentile ranks only
  become meaningful after the product has enough active users.
- **Social functions:** accounts and authorization are prerequisites for chat,
  profiles, shared lists, comments, and visibility controls.

## 17. References

- Shelf Life project brief supplied in the studio materials
- Open Library API: `https://openlibrary.org/developers/api`
- Open Library Covers API: `https://openlibrary.org/dev/docs/api/covers`
- FastAPI documentation: `https://fastapi.tiangolo.com/`
- Model Context Protocol documentation: `https://modelcontextprotocol.io/`
- Semgrep documentation: `https://semgrep.dev/docs/`
