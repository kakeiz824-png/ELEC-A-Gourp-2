# Shelf Life - Design Document

## 1. Overview

Shelf Life is a personal reading tracker. Readers organize books across three shelves:
`reading`, `finished`, and `wishlist`. They can add ratings and optional review text,
view reading statistics, and move books as their reading status changes.

The main interaction is intentionally simple: the user types only a title, and the
application attempts to fill in the author, ISBN, cover URL, and publication year.
The current application calls the keyless Open Library API directly through
`app/openlibrary.py` and falls back to `seed/books.json` when the live catalogue is
unavailable or has no match. The course-required MCP server has not been implemented
yet. M2 will expose the same lookup capabilities through MCP while preserving the
current normalization and fallback behavior.

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
- **Normal demo mode:** the default `openlibrary` backend retrieves live metadata and
  uses the seed catalogue as a fallback.
- **Reliable offline demo mode:** set `SHELF_LIFE_LOOKUP_BACKEND=seed`. The demo title
  is stored in `seed/books.json`, so this mode does not depend on network access.
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

### M1 acceptance criteria

| Story | Done when |
|---|---|
| Add a book by title | A valid title and shelf create one stored book; a blank or overlong title is rejected. |
| Choose a shelf | `reading`, `finished`, and `wishlist` are accepted; any other value is rejected. |
| Move a book | The selected book appears on the new shelf; a missing book returns 404. |
| View metadata | Author, ISBN, year, and cover are shown when lookup supplies them. |
| Add a rating | Ratings from 1 to 5 are stored; values outside that range are rejected. |
| Add optional review text | A rating can be saved with or without text; overlong text is rejected. |
| Delete a book | The selected book is no longer returned after deletion. |
| Cascade reviews | Deleting a book also removes every review belonging to it. |
| Filter by shelf | `GET /books?shelf=...` returns only books on the requested shelf. |
| View statistics | Totals, shelf counts, review count, and average rating reflect stored data. |
| Survive lookup failure | The title is saved with `details_pending = true` when no metadata source succeeds. |
| Retry enrichment | A pending book can be looked up again and updated when metadata becomes available. |

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

The team confirmed this MoSCoW scope on July 28, 2026. Future changes to the current
milestone scope should be agreed by the team and recorded in this document.

### Must Have

1. [x] **Book and shelf core:** create, read, filter, move, enrich, and delete books
   across `reading`, `finished`, and `wishlist`.
2. [x] **Lookup and fallback:** retrieve normalized book metadata through the current
   direct Open Library client, fall back to `seed/books.json`, and preserve unmatched
   titles with `details_pending`.
3. [x] **Ratings, reviews, persistence, and validation:** store data in SQLite, validate
   user input, and cascade-delete reviews with their book.
4. [ ] **Required M2 MCP integration:** expose `search_book(title)` and
   `get_book_details(isbn)` through an MCP server and connect the existing lookup
   boundary to those tools.
5. [ ] **Required M2 verification:** mock the MCP tools in automated tests, run the
   full test suite, and run and review the required security scan.

### Should Have

1. [x] Display cover images with a placeholder fallback.
2. [x] Show book totals, shelf counts, review count, and average rating.
3. [x] Provide a usable three-column browser interface, health endpoint, and
   interactive API documentation.

### Could Have

1. [ ] Show three related-book recommendations using author or subject similarity.
2. [ ] Add discovery pages for normalized fiction/nonfiction categories and author
   catalogues or biographies.

These are M2 stretch candidates, not commitments. The team will choose a realistically
sized extension only after the required MCP, testing, and security work is planned.

### Won't Have in the current M2 scope

1. A complete account, friendship, and chatroom system.
2. A production AI conversational search and recommendation assistant.
3. A complete percentile leaderboard, reward economy, and achievement platform.
4. A complete social platform containing shared lists, public profiles, comments,
   ratings, and fine-grained privacy controls.

The eight team ideas remain in the future roadmap. The Won't Have list prevents them
from being treated as current commitments. Social and AI features require additional
authentication, authorization, privacy, moderation, cost, and evaluation design.

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

### 7.2 Stable lookup boundary across HTTP, seed, and future MCP

The application depends on one internal `lookup(title)` interface. The current default
implementation calls Open Library directly through `app/openlibrary.py` and falls back
to `seed/books.json`. M2 will connect an MCP client through the same lookup boundary.
Routers must not depend on whether metadata came from direct HTTP, MCP, or the seed.

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
                  +-------+------------------+
                  |                          |
       [Current Open Library HTTP]   [seed/books.json fallback]
                  |
                  v
          [Open Library API]

Future M2 path:
[lookup(title)] -> [MCP client] -> [Open Library MCP server]
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

## 12. Current Repository Structure

```text
app/
  __init__.py
  db.py
  details.py
  lookup.py
  main.py
  models.py
  openlibrary.py
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
  test_openlibrary.py
  test_reviews.py
CLAUDE.md
DESIGN.md
GIT_GUIDE.md
README.md
requirements.txt
```

No MCP server directory exists yet. It will be added during M2 after the team confirms
the tool schemas and transport.

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

- [x] Implement the direct Open Library HTTP functions `search_book` and
  `get_book_details`.
- [x] Normalize external responses into `BookDetails`.
- [x] Add direct HTTP timeouts, failure mapping, seed fallback, and mocked HTTP tests.
- [ ] Define normalized MCP tool schemas.
- [ ] Expose `search_book` and `get_book_details` as MCP tools.
- [ ] Connect the MCP client through the existing lookup boundary.
- [ ] Add isolated mocked tests for the MCP tools and client.
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
- Direct Open Library response normalization, failures, and seed fallback.
- Database connections used safely across FastAPI worker threads.

The earlier M1 seed-only snapshot was locally verified with:

```powershell
..\.venv\Scripts\python.exe -m pytest --basetemp=.test-tmp
```

The earlier M1 seed-only snapshot passed **38 tests with 1 deprecation warning**.

Final verification of the current GitHub `main` was completed on July 28, 2026,
using Python 3.13.2 at commit `bb8f350`. The full suite passed **59 tests with
1 StarletteDeprecationWarning**. The live Open Library lookup and the complete
browser workflow were also verified manually.

### M2 test requirements

- Unit-test each MCP tool with mocked Open Library responses.
- Test missing fields, empty results, invalid ISBNs, timeouts, and upstream errors.
- Confirm external failures still create a `details_pending` book.
- Never call the real Open Library API from the automated test suite.

## 15. Security Considerations

### Implemented in the current application

- [x] Pydantic validation for title, shelf, rating, and review length.
- [x] SQLite checks for shelf and rating values.
- [x] Parameterized SQL.
- [x] Foreign-key cascade behavior.
- [x] CORS allowlist controlled by `SHELF_LIFE_ORIGINS`.
- [x] Browser rendering of user content through `textContent`.
- [x] No required API key for Open Library.
- [x] Timeout on outbound Open Library requests.
- [x] Safe handling of HTTP failures and malformed or incomplete responses.
- [x] Automated network tests use mocks instead of the live service.

### Required for the M2 MCP integration

- [ ] Validate MCP tool arguments and bound input sizes.
- [ ] Review the selected MCP transport and error mapping.
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
