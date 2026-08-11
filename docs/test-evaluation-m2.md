# M2 Test Suite Evaluation — Shelf Life

**Date:** 2026-08-11
**Verified:** 210 tests pass, 0 failures, 0 skipped, 1 deprecation warning (Starlette/httpx, not an error). Command: `.venv\Scripts\python.exe -m pytest --basetemp=.test-tmp -q`

This table satisfies the M2 requirement to record the origin of every test and classify each AI-generated test. The **Origin** column is the team's to confirm: the repository does not carry per-test labels, so entries marked `[TEAM]` were reconstructed from file content and must be corrected if wrong.

## Test origin and evaluation

| Test file | Coverage | Origin | Evaluation | Rationale |
|-----------|----------|--------|------------|-----------|
| `tests/test_books.py` | Book CRUD, shelves, duplicate ISBNs, enrich, delete cascade, cover fallback | [TEAM] | GOOD | Exercises real routes against a temp database; covers validation, 404, 409, and UI contract behavior. |
| `tests/test_reviews.py` | Rating 1–5, review upsert, cascade delete, missing book 404 | [TEAM] | GOOD | Asserts the business rules that define the data model. |
| `tests/test_lookup.py` | Seed ranking, normalization, caching, fallback, ISBN identity, no-query/ISBN log leak | [TEAM] | GOOD | Includes the demo input, cache behavior, and the log-hygiene regression tests added 2026-08-11. |
| `tests/test_openlibrary.py` | HTTP response conversion, timeouts, malformed payloads, backend env | [TEAM] | GOOD | Mocks every response; proves normalization and failure behavior. |
| `tests/test_mcp_server.py` | Tool registration, STDIO start, paging, validation, error mapping, `get_book_details` behavior | [TEAM] | GOOD | Drives FastMCP in-memory and STDIO clients with mocked Open Library functions; behavior tests for `get_book_details` added 2026-08-11. |
| `tests/test_mcp_client.py` | Default `mcp` backend, structured→`BookDetails` conversion, failure mapping | [TEAM] | GOOD | Locks the integration boundary between app and MCP. |
| `tests/test_author_search.py` | Author index filtering, initial handling, ranking | [TEAM] | GOOD | Covers the author-vs-title search distinction. |
| `tests/test_recent.py` | Recent-books endpoint behavior | [TEAM] | GOOD | Covers the recent endpoint added via PR #9. |
| `tests/test_search_paging.py` | Paged search results and offset handling | [TEAM] | GOOD | Locks the paging contract used by the browser. |
| `tests/test_migrations.py` | Legacy duplicate merge, review de-dup, identity index | [TEAM] | GOOD | Real migration scenarios against old-shaped databases. |
| `tests/test_turso_adapter.py` | libSQL row access, cursor iteration, stats, unique constraint | [TEAM] | GOOD | Regression test for the exact `collect_stats()` pattern that broke on libSQL cursors. |

## Example of a problem found and fixed in a test/AI output

`tests/test_turso_adapter.py` (docstring): the libSQL cursor is not directly iterable, while `app/services/stats.py::collect_stats()` used `for row in connection.execute(...)`. The adapter (`app/db.py::_TursoCursor.__iter__`) materializes rows via `fetchall()`, and the test locks that in against a real in-memory libSQL engine.

## Missing cases checked

- Every external call is mocked; `tests/conftest.py` forbids real Open Library access.
- `get_book_details` now covers success, blank, overlong, no-match, unavailable, and unexpected-failure logging (added 2026-08-11).
- Fallback warnings are asserted to contain neither user queries nor ISBNs (added 2026-08-11).
- No skipped tests: pytest reports 0 skips.