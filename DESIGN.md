# Shelf Life - Design Document

## 1. Overview

Shelf Life is a personal reading tracker. Readers organize books across three shelves:
`reading`, `finished`, and `wishlist`. They can add ratings and optional review text,
view reading statistics, and move books as their reading status changes.

The main interaction is intentionally simple: the user types one thing, reviews the
ISBN-bearing catalogue matches a page at a time, and selects the correct edition. Nothing is
stored until the user makes that selection; the application then fills in the author,
ISBN, cover URL, and publication year.

That one thing may be a book title or an author's name, and a Title/Author selector
beside the box says which. Two indexes are needed because Open Library's title index
answers an author's name with books written *about* them: searching "George Orwell" by
title returns his biographies and a SparkNotes guide, never Nineteen Eighty-Four.
Results are paged rather than capped, so a search for Harry Potter can show all seven
novels.

The current application calls the `search_book`, `search_by_author`, and
`get_book_details` MCP tools through `app/mcp_client.py`. The MCP server reuses the keyless Open Library client and
the application falls back to `seed/books.json` when MCP, the live catalogue, or the
match is unavailable. A direct `openlibrary` backend remains available for focused
diagnostics.

## 2. Demo Contract

- **Audience:** students and hobby readers who want a lightweight way to track books.
- **Problem:** manually entering every author, ISBN, year, and cover makes reading
  trackers tedious to maintain.
- **Magic moment:** the user types `The Hobbit`, presses **Search books**, selects the
  correct result, and a complete card appears with Tolkien, 1937, an ISBN, and a cover.
- **Exact demo input:** title = `The Hobbit`, shelf = `reading`.
- **Second demo input:** switch the selector to Author and enter `Ursula K. Le Guin`.
  The results are her own novels, not the books written about her that a title search
  returns.
- **Expected output:** the search itself changes no shelf; selecting one candidate
  creates one populated card on the Reading shelf.
- **Additional demo actions:** add a rating and review, move the book to Finished,
  refresh the page, and confirm the data persists.
- **Failure behavior:** if lookup and the seed fallback cannot supply an ISBN,
  no book is stored and the interface asks the user to check the title or retry later.
- **Normal demo mode:** the default `mcp` backend retrieves live metadata through the
  MCP tool and uses the seed catalogue as a fallback.
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
11. As a reader, I want a title without a verified ISBN to be rejected so that
    unverified records are not added to my shelves.
12. As a reader with legacy pending data, I want to retry enrichment.
13. As a reader, I want a duplicate ISBN to be rejected so that one book cannot
    appear on two reading-status shelves.
14. As the single user, I want a later review submission to update my existing
    review instead of creating another personal review.
15. As a reader, I want to page through the matching editions before adding a book so
    that I can choose the correct title and ISBN, however many matches there are.

### M1 acceptance criteria

| Story | Done when |
|---|---|
| Search before adding | A valid query returns one page of distinct ISBN-bearing candidates, with the total and page count, and creates no stored row. |
| Add a selected book | Selecting a candidate and shelf creates exactly that ISBN; a blank or overlong title is rejected. |
| Choose a shelf | `reading`, `finished`, and `wishlist` are accepted; any other value is rejected. |
| Move a book | The selected book appears on the new shelf; a missing book returns 404. |
| View metadata | Author, ISBN, year, and cover are shown when lookup supplies them. |
| Add a rating | Ratings from 1 to 5 are stored; values outside that range are rejected. |
| Add optional review text | A rating can be saved with or without text; overlong text is rejected. |
| Delete a book | The selected book is no longer returned after deletion. |
| Cascade reviews | Deleting a book also removes every review belonging to it. |
| Filter by shelf | `GET /books?shelf=...` returns only books on the requested shelf. |
| View statistics | Totals, shelf counts, review count, and average rating reflect stored data. |
| Reject unverifiable books | A lookup result without an ISBN returns 404 and creates no row. |
| Retry enrichment | A legacy pending book can be looked up again and updated when an ISBN becomes available. |
| Reject duplicate books | A normalized ISBN can have only one tracked row; a duplicate add returns 409 and leaves its current shelf unchanged. |
| Allow same-title books | Books with the same title and different ISBNs can both be tracked. |
| Update personal review | A book has at most one review; a later submission updates its rating and text. |

### Future user stories

1. As a reader, I want three related-book suggestions after selecting a book.
2. As a reader, I want to browse books by fiction and nonfiction categories.
3. As a reader, I want to view an author's biography alongside their books.
   Searching an author and seeing their books is implemented; the biography is not.
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
2. [x] **Lookup and fallback:** retrieve normalized book metadata through the MCP
   search tool, fall back to `seed/books.json`, and require an ISBN before creation.
3. [x] **Ratings, reviews, persistence, and validation:** store data in SQLite, validate
   user input, and cascade-delete reviews with their book.
4. [x] **Required M2 MCP integration:** `search_book(title)`,
   `search_by_author(author)`, and `get_book_details(isbn)` are exposed and connected
   through the existing lookup boundary.
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

### 7.2 Stable lookup boundary across MCP, HTTP, and seed

The application depends on one internal `lookup(title)` interface. The default
implementation calls `search_book` through `app/mcp_client.py`; it converts structured
MCP data into `BookDetails` and falls back to `seed/books.json`. The direct HTTP backend
remains available for diagnostics. Routers do not depend on whether metadata came from
MCP, direct HTTP, or the seed.

### 7.3 Failure-safe creation

Lookup is a prerequisite for storing a new book because ISBN is the product's sole
book identity. If lookup and seed fallback cannot supply an ISBN, `POST /books`
returns 404 and stores nothing. Existing legacy pending rows are preserved during
database migration and can still use the enrichment endpoint.

### 7.4 SQLite for the M1 walking skeleton

SQLite provides persistence, foreign keys, checks, and simple local setup. Each request
receives its own connection, foreign keys are enabled, and SQL parameters are used.

### 7.5 Recommendations must match available evidence

Early recommendations can use the same author or Open Library subjects. The product
must not label these as "people who liked this also liked" until real user-interaction
data exists.

### 7.6 The user says whether they typed a title or an author

The search box is paired with a Title/Author selector. The server is told which index
to query and never infers it.

Inferring it was built first, and removed. One box was tried on the grounds that
making the user classify their own input is friction on the interaction the product is
built around. Both searches ran and the results were merged, with a guaranteed slot in
the merged list earned by naming an author in full. Two failures killed it, and both
are the same failure:

- `author=Dune` returns 131 real authors named Dune, so searching Dune offered a TEAS
  practice-test book by Linda Dune. The full-name rule was added to fix this.
- `author=Harry Potter` returns a real legal historian named Harry Potter, and the
  query *is* his full name, so the rule granted him slots 2 and 4 and pushed two of
  the novels out of a five-item list.

No rule separates those cases from a genuine author search, because in each pair both
readings are true: Harry Potter is a series and a person, Dune is a novel and a
surname. The ambiguity is in the input, so it is resolved where the knowledge is, by
the person typing. One click buys correctness that no heuristic can, and it halves
catalogue traffic because only one index is queried.

### 7.7 Results are paged, and an addition is confirmed by ISBN

Capping candidates at five hid books: a search for Harry Potter could not show seven
novels. Results are paged instead, ten to a page, with the page count taken from the
catalogue's own total.

Paging broke how an addition was confirmed. `POST /books` re-ran the search and looked
for the submitted ISBN among the results, which is sound when there is one page of
five and wrong once there are 311: the chosen book may have come from page seven, and
Open Library's relevance order shifts between requests, so a legitimate add could 404.

An ISBN identifies a book, so the ISBN is now resolved directly through
`get_book_details`. That has no such failure mode, needs no search state in the
request, and keeps the property the re-search existed for: metadata comes from the
catalogue, never from the client. It also required exposing the third planned M2 tool,
which is why `get_book_details` is now implemented rather than pending.

Future work: group editions under a work. Open Library exposes a work key
(`key`, e.g. `/works/OL82563W`) that would support it. One book can have
several editions with different ISBNs, and tracking each edition is deliberate
(`CLAUDE.md`: allow books with the same title when their ISBNs differ), but a
broad author search surfaces many editions and translations of the same work.
Grouping them would make the result list easier to scan.

## 8. System Architecture

```text
[Browser: HTML/CSS/JavaScript]
              |
              v
[FastAPI routes and validation]
       |                 |
       v                 v
[SQLite database]   [services/search.py: one paged search]
                          |
                          v
                    [lookup boundary]
                          |
                  +-------+------------------+
                  |                          |
          [MCP client adapter]       [seed/books.json fallback]
                  |
                  v
   [FastMCP search_book / search_by_author / get_book_details]
                  |
                  v
        [Open Library HTTP client]
                  |
                  v
          [Open Library API]
```

## 9. Data Model

### User

| Field | Type | Rules |
|---|---|---|
| `id` | Integer | Primary key |
| `google_sub` | Text | Google subject id; unique, keys the row on sign-in |
| `email` | Text | From the Google profile |
| `name` | Text or null | Display name from the Google profile |
| `picture` | Text or null | Avatar URL from the Google profile |
| `created_at` | Text timestamp | Assigned by SQLite |

### Book

| Field | Type | Rules |
|---|---|---|
| `id` | Integer | Primary key |
| `user_id` | Integer | Owner; foreign key to User, cascade on delete |
| `title` | Text | Required, 1-300 characters after trimming |
| `author` | Text or null | Filled by lookup when available |
| `isbn` | Text or null | Required for new books; null is retained only for legacy compatibility |
| `cover_url` | Text or null | Filled by lookup when available |
| `year` | Integer or null | First publication year when available |
| `shelf` | Text | `reading`, `finished`, or `wishlist` |
| `details_pending` | Integer/Boolean | True when details still need enrichment |
| `identity_key` | Text | Internal normalized ISBN, unique per user (`(user_id, identity_key)`) |
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

Each Book belongs to exactly one User, and all book, review, and stats queries
are scoped to the signed-in user's rows. One Book has zero or one Review; a later
submission updates the existing Review. A Review belongs to exactly one Book (and
so, transitively, to that Book's owner). Two users may each track the same ISBN
independently, since the identity guard is `(user_id, identity_key)`.

## 10. Current API

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/` | Render the three-shelf interface |
| `GET` | `/health` | Return application health |
| `GET` | `/books` | List books; optionally filter with `?shelf=` |
| `GET` | `/books/search` | Return one page of distinct ISBN-bearing candidates without storing them |
| `POST` | `/books` | Add the selected ISBN; return 404 without an ISBN or 409 when it already exists |
| `GET` | `/books/{id}` | Return one book with its reviews |
| `PATCH` | `/books/{id}/shelf` | Move a book to another shelf |
| `POST` | `/books/{id}/enrich` | Retry lookup for a book |
| `DELETE` | `/books/{id}` | Delete a book and its reviews |
| `GET` | `/books/{id}/reviews` | List reviews for a book |
| `POST` | `/books/{id}/reviews` | Create or update the personal rating and review |
| `GET` | `/authors` | Return one author's profile for `?name=`; `found=false` with null fields when none is available |
| `GET` | `/stats` | Return counts and average rating |

M1 does not provide a general `PATCH /books/{id}` endpoint or separate update/delete
endpoints for an individual review. Reposting to the review collection updates the
single user's existing review.

### Search parameters

`GET /books/search` requires exactly one of `title` and `author`. Sending neither, or
both, returns 422: the caller has to say which catalogue index to query, because
strings like `Dune` and `Harry Potter` name both a book and a person.

| Parameter | Meaning | Default |
|---|---|---|
| `title` | Search book titles | — |
| `author` | Search book authors | — |
| `page` | 1-based page number | `1` |
| `per_page` | Candidates per page, 1 to 50 | `10` |

### Example search response

```json
{
  "items": [
    {
      "title": "Nineteen Eighty-Four",
      "author": "George Orwell",
      "isbn": "9780451524935",
      "cover_url": "https://covers.openlibrary.org/b/isbn/9780451524935-M.jpg",
      "year": 1949
    }
  ],
  "page": 1,
  "per_page": 10,
  "pages": 43,
  "total": 421
}
```

`total` and `pages` come from the catalogue's count of what it matched. Candidates
without an ISBN are dropped after a page is fetched, so a page can hold fewer than
`per_page` items while later pages still exist.

### Example add request

```json
{
  "title": "Nineteen Eighty-Four",
  "isbn": "9780451524935",
  "shelf": "reading"
}
```

The ISBN identifies the book, so the server resolves it against the catalogue and uses
what it finds. Nothing else in the request is trusted: `title` is used only when no
ISBN is given, the contract that existed before the search UI. An ISBN the catalogue
does not know returns 404 and stores nothing.

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

## 11. M2 MCP Design

### External service

Open Library is keyless and provides title search, edition data, author data, subjects,
and cover identifiers.

### MCP tools

Studio 5 requires the team to design 5-10 AI-facing tool signatures and implement
at least one tool end to end. The implemented Shelf Life catalogue tools are
`search_book`, `search_by_author`, and `get_book_details`; the remaining signatures
are planned and must not be described as implemented until their code and tests
exist.

| Tool | When the AI should use it | Parameters | Returns |
|---|---|---|---|
| `search_book` | The user gives a full or partial title and wants likely matches. | `title: str`, `limit: int = 5`, `offset: int = 0` | One page of normalized Open Library matches, and the total match count. |
| `search_by_author` | The user names a writer rather than a book and wants the books that writer wrote. | `author: str`, `limit: int = 5`, `offset: int = 0` | One page of normalized Open Library matches, and the total match count. |
| `get_book_details` | The user provides an ISBN, or has selected one search result and wants that edition's details. | `isbn: str` | Title, author, year, ISBN, and cover for that one book. |
| `get_author_details` | The user wants to know about a writer -- biography and life dates -- rather than a list of their books. | `name: str` | Name, biography, birth/death dates, and photo when the catalogue has them. |
| `list_shelf` | The user asks what is currently on one personal shelf. | `shelf: str` | Books on Reading, Finished, Wishlist, or all shelves. |
| `get_reading_stats` | The user asks for totals, progress, reviews, or average rating. | none | Current shelf counts, review count, and average rating. |
| `add_book` | The user explicitly asks to save a title to their tracker. | `title: str`, `shelf: str = "reading"` | The stored book and selected shelf. |
| `move_book` | The user explicitly asks to change a tracked book's reading status. | `book_id: int`, `shelf: str` | The updated book and shelf. |
| `add_review` | The user explicitly asks to save a rating or review for a tracked book. | `book_id: int`, `rating: int`, `text: str \| None` | The saved review. |

`delete_book` is intentionally not exposed during the first MCP iteration because
it is destructive and the course exercise has not yet defined a confirmation
workflow for destructive tools.

#### Studio 5 implemented tool

`search_book(title: str, limit: int, offset: int)` and
`search_by_author(author: str, limit: int, offset: int)`:

- trim the query and accept 1-300 characters;
- accept a `limit` of 1 to 50 and a non-negative `offset`, and report the total match
  count so a caller can page without guessing;
- reuse `app.openlibrary.search_book` and `app.openlibrary.search_author` instead of
  duplicating HTTP code;
- return at most `limit` formatted, AI-readable results, defaulting to five;
- also return structured book data for the web application;
- return clear no-result and temporary-unavailable messages; and
- do not reveal raw exceptions or Open Library response JSON.

`search_by_author` queries Open Library's `author=` index rather than `title=`, and
drops results whose primary author is somebody else, which is how anthologies the
author only contributed one story to are kept out. That filter never empties a result
set: if nothing survives it, the unfiltered results are returned, so an author
credited only as a co-author ranks low instead of vanishing.

### Integration boundary

`app/mcp_client.py` converts structured MCP responses into the existing
`BookDetails` shape. Routers reach the catalogue through `app/services/search.py` and
the `lookup` module, and do not depend on raw Open Library JSON or MCP response
objects.

### Transport

Use FastMCP with STDIO for Inspector and desktop MCP clients. The local web
application uses FastMCP's in-memory MCP transport so it exercises tool discovery,
validation, serialization, and protocol handling without starting a new subprocess
for every book addition.

### Manual integration evidence

On 2026-07-28, MCP Inspector v2 connected to the STDIO server, discovered
`search_book`, and returned five live Open Library matches for `The Hobbit`. The
colored Shelf Life page was then run with the default `mcp` backend; adding the same
title produced live MCP metadata on the Reading shelf. Claude Desktop remains
unverified because the team's new Claude account could not access the service.

On 2026-08-05, author search and paging were verified against the live catalogue
through the running application on the default `mcp` backend, not through Inspector.
An author search for `George Orwell` returned Nineteen Eighty-Four and Animal Farm,
and `J. K. Rowling` returned all seven Harry Potter novels on page 1 of 43. A title
search for `Harry Potter` returned the seven novels on page 1 of 311, and page 2
returned nine candidates rather than ten because one lacked an ISBN, which is the
documented short-page behaviour. Every ISBN offered on the first page of four separate
searches resolved through `get_book_details`, 40 of 40, which is what confirming an
addition depends on. Inspector discovery of the second and third tools remains to be
recorded.

## 12. Current Repository Structure

```text
app/
  __init__.py
  db.py
  details.py
  lookup.py
  main.py
  mcp_client.py
  models.py
  openlibrary.py
  routers/
    __init__.py
    books.py
    reviews.py
  services/
    __init__.py
    books.py
    reviews.py
    search.py
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
  test_author_search.py
  test_books.py
  test_lookup.py
  test_search_paging.py
  test_mcp_client.py
  test_mcp_server.py
  test_openlibrary.py
  test_reviews.py
mcp_server/
  __init__.py
  server.py
CLAUDE.md
DESIGN.md
GIT_GUIDE.md
README.md
requirements.txt
```

The Studio 5 server exposes `search_book`, `search_by_author`, and
`get_book_details` through FastMCP over STDIO. The FastAPI application calls the same
tools through its in-memory MCP client adapter and preserves seed fallback.

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
- [x] Define seven Studio 5 MCP tool signatures.
- [x] Expose and test `search_book` as the first end-to-end FastMCP tool.
- [x] Expose `get_book_details` as the second Open Library MCP tool.
- [x] Connect the MCP client through the existing lookup boundary.
- [x] Add isolated mocked tests for the first MCP tool.
- [x] Add isolated mocked tests for the first MCP client adapter.
- [x] Add isolated mocked tests for the remaining MCP tools.
- [x] Run the full test suite after the first MCP tool and web integration.
- [x] Run Semgrep and review findings.

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
- Verify `POST /books` uses normalized data returned through the MCP client.
- Test missing fields, empty results, invalid ISBNs, timeouts, and upstream errors.
- Confirm external failures and ISBN-less results create no book.
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

- [x] Validate `search_book` arguments and bound input sizes.
- [x] Review the STDIO/in-memory MCP transports and error mapping.
- [x] Avoid logging sensitive user-provided content unnecessarily.
- [x] Run Semgrep and manually review its findings.

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
