# PLAN.md - Review response plan

Written 2026-08-06. Revised 2026-08-06 after PR #13 merged (M2 evidence: CI workflow, Semgrep report, AI usage log, README/CLAUDE updates). Covers the error-handling issue we found ourselves, the code
review comments from Emma Zhou, and finding books by author name.

Every claim below was checked against the working tree rather than taken from the
review text, because the review was written against the committed code and some of
the files have changed since. Where a review comment's stated cause or consequence
did not hold up, the correction is recorded with the evidence. In each of those
cases the fix is still worth making; only the reason for making it changes.

## Working tree state - read this first

The author search and paged search results are **already implemented but not
committed**. `git status` shows 20 modified files plus one new test file.

One clarification, checked against the repository on 2026-08-06: basic author
search (`search_author` in `app/openlibrary.py` and the `search_by_author` MCP
tool) is already on `main` via PR #12. What is not on `main` is the newer
working-tree work: the Title/Author selector, paged results (ten per page),
`get_book_details` confirmation on `POST /books`, and the associated tests.

Three consequences for this plan:

1. The line numbers in Emma's review and in our own error-handling finding refer to
   the committed version. They have shifted. Both numbers are given below.
2. Item 2 is not development work. It is shipping work.
3. `origin/main` has advanced to `e842386` (PR #13 merged the M2 evidence). Rebase
   the working tree onto `origin/main` before committing Item 2.

Nothing in this plan should be started before Item 2 is resolved, or the same files
will be edited twice.

## Item 1 - Missing error handling in the book card event listeners

Our own finding. This is the one real defect in the list.

### What

Four event listeners inside `buildCard` in `static/app.js` call the API without
handling a failure:

| Action | Committed line | Current line |
|---|---|---|
| Move a book to another shelf | 171 | 192 |
| Retry the metadata lookup | 179 | 200 |
| Delete a book | 186 | 207 |
| Save a rating and review | 207 | 228 |

### Evidence

`api()` throws on every non-2xx response, by design:

```js
// static/app.js:42
if (!response.ok) {
  ...
  throw error;
}
```

None of the four listeners has a `try`/`catch`. So a failed request rejects the
listener's promise, and every statement after the `await api(...)` is skipped. The
three consequences we listed are all real and follow directly:

- **The loading message stays on screen.** The retry listener sets
  `Looking up "…"` before the call and clears it after. On failure the clearing
  line at `static/app.js:203` never runs, so the working message is permanent
  until the next action.
- **The user is not told anything.** The rejection surfaces only as an unhandled
  promise rejection in the browser console.
- **A change can look applied when it was not.** The shelf dropdown is the worst
  case: the browser has already repainted `moveSelect` with the newly chosen
  shelf, and `refresh()` at `static/app.js:197` is what would have re-rendered it
  from the server. Skip that and the card shows a shelf the database never stored.

### Plan

1. Add a small helper next to `api()` that wraps one action: report through
   `setHint(..., "error")` on failure, and re-render from the server either way so
   the card can never keep optimistic state.

   ```js
   /** Run one card action, reporting failure and re-syncing either way. */
   async function cardAction(work, failureMessage) {
     try {
       await work();
     } catch (error) {
       setHint(error.message || failureMessage, "error");
     } finally {
       await refresh();
     }
   }
   ```

   `refresh()` in the `finally` is the part that fixes the third symptom: the
   dropdown snaps back to the stored shelf when the write failed.

2. Route all four listeners through it, each with a message naming the action that
   failed, so "Could not move that book." is distinguishable from "Could not save
   your review."

3. Apply it to the remaining listeners that call the API, as the finding asks. The
   audit of those:
   - `retryButton` (line 200) - in scope, listed above.
   - `reviewForm` submit (line 228) - in scope, listed above.
   - `moveSelect` change (line 192), delete button (line 207) - in scope.
   - `chooseButton` in `buildSearchResult` - **already handled**, has
     `try`/`catch`/`finally` and re-enables its button. It is the pattern to copy.
   - `addForm` submit and the pagination buttons - **already handled** through
     `runSearch`, which has `try`/`catch`/`finally`.
   - `cover` error listeners - no API call, only a placeholder swap. Nothing to do.
   - `reviewButton` (line 221) - toggles form visibility, no API call.

   So the four in the table are the complete set of unhandled ones.

4. If `refresh()` itself fails, `cardAction` would throw from the `finally`. Guard
   it, or the fix reintroduces the bug it removes on a network outage.

### Files

`static/app.js`.

### Tests

The suite has no JavaScript tests and the project has no JS test runner, so adding
one is a larger decision than this fix. Verify by hand against a running app:

1. Stop the API, then use each of the four controls. Each must show an error in the
   hint line, and the shelf dropdown must snap back to its stored value.
2. Restart the API and confirm all four still work normally.

Record the result in this file when done. Do not claim it passes without running
it.

### Done when

All four listeners report failures, no control can display state the server did not
confirm, and the manual check above has been run and recorded.

## Item 2 - Finding books by author name

### Status

Implemented in the working tree, verified against the live catalogue, **not
committed**.

- Open Library's `author=` index is queried through `app/openlibrary.py`
  `search_author`, exposed as the `search_by_author` MCP tool, reached through the
  `lookup` boundary, with the seed fallback preserved.
- A Title/Author selector next to the search box tells the server which index to
  use. Two earlier attempts to infer it from the query failed; see `DESIGN.md`
  section 7.6.
- Results are paged, ten per page, so a search for Harry Potter shows all seven
  novels instead of the first five matches.
- `POST /books` confirms a submitted ISBN through `get_book_details` instead of
  re-running the search, because a chosen candidate may have come from page seven.
- 159 tests pass. Semgrep reports no findings over 255 rules, including the two new
  files that its default git-tracked scope would have skipped.

### Remaining work

1. Finish the interrupted browser check: the Title/Author selector and the
   Previous/Next controls have been verified as rendered and as calling the right
   endpoints, but have not been clicked in a browser.
2. Rebase onto the latest `origin/main` (`e842386` or newer), then commit and push.
3. Deployment is **not automatic**. Pushing `main` alone has not updated Render: the
   cover-fix commit `8c900ab` has been on `main` since 2026-08-05, yet the public
   site still serves the old `app.js` (no version parameter; `cover-placeholder.svg`
   returns 404; verified 2026-08-06). After pushing, someone must trigger
   **Manual Deploy → Deploy latest commit** in Render (or fix auto-deploy) before
   the change is live.
4. Hard-refresh before testing the deployed app. The HTML structure changed, so a
   cached `app.js` will not merely behave differently, it will fail against the new
   markup.
5. Record Inspector discovery of `search_by_author` and `get_book_details` in
   `DESIGN.md`, which currently notes it as outstanding.

## Item 3 - Input sanitisation in the MCP search tools

Emma Zhou, marked critical.

### The comment

Only a blank check and a length limit are applied. No sanitisation of leading or
trailing special symbols, repeated whitespace, line breaks or control characters.
Raw input reaches the Open Library API.

### What is true

The gap is real. `mcp_server/server.py` does `query = raw.strip()` and nothing
further, so `"Harry\n\nPotter"` and `"Harry    Potter"` are passed through as
typed.

### What is not

The stated consequence of "malformed upstream API requests" does not hold. The
query is passed as an httpx `params` value, so httpx percent-encodes it. A newline
leaves as `%0A`; it cannot break the request line or inject a parameter. We should
not describe this as a request-integrity problem, because it isn't one, and a fix
justified on false grounds is hard to review.

What remains, and is worth fixing:

- **Match quality.** Repeated whitespace and stray control characters are sent to
  the search index as part of the query and can only hurt the match.
- **Log and cache noise.** Two queries that are the same book become two distinct
  strings.

That is a nitpick-to-suggestion in our judgement, not critical. Recording the
disagreement rather than silently re-grading it.

### Plan

1. Add one normalisation helper in `mcp_server/server.py`, applied straight after
   the strip and before the length check, so the limit is measured on what is
   actually sent:
   - strip Unicode control characters and other non-printables;
   - collapse any run of whitespace, including newlines and tabs, to one space.
2. Apply it in `_search_result`, which both search tools already share, so the two
   tools cannot drift apart. `get_book_details` keeps its own narrower rule: an
   ISBN should have everything except digits and `X` removed, which
   `normalise_isbn` in `app/details.py` already does.
3. Do not strip punctuation. Titles legitimately contain `:`, `'`, `&` and `.`, and
   `_author_tokens` already ignores punctuation when matching author names.

### Files

`mcp_server/server.py`. Possibly `app/details.py` if the helper belongs beside
`normalise`.

### Tests

Add to `tests/test_mcp_server.py`:

- a query with newlines, tabs and repeated spaces reaches the search function as
  one single-spaced string;
- a query of control characters only is rejected as blank, and does not call the
  catalogue;
- the length limit is applied after collapsing, so 400 spaces plus a short title
  is accepted;
- a title containing `:` and `'` is passed through unchanged.

### Done when

Both search tools normalise identically, the tests above pass, and the length limit
is measured on the normalised string.

## Item 4 - Generic exception handling in the MCP tools

Emma Zhou, marked suggestion.

### The comment

Only `LookupUnavailable` is caught. Timeouts, connection failures, HTTP 4xx/5xx and
JSON parsing failures are unhandled, and an uncaught exception crashes the MCP
server process and disconnects the client.

### What is true

`_search_result` and `get_book_details` catch only `LookupUnavailable`, so anything
else propagates out of the tool function.

### What is not

Both stated causes were checked and do not hold.

**The listed network errors are already handled.** `app/openlibrary.py:83` catches
`httpx.HTTPError`, which is the base class of timeouts, connection failures and the
`HTTPStatusError` raised by `raise_for_status`, and line 85 catches `ValueError`,
which covers JSON decode failures. All of them are converted to
`LookupUnavailable`, which the tools do catch.

**The server does not crash.** Tested directly by making the search function raise
`RuntimeError` through FastMCP's in-memory client:

```
is_error: True
text    : Error calling tool 'search_book': an unexpected bug, not a LookupUnavailable
structured: None
後續呼叫仍可用: Error: isbn must not be blank.
```

FastMCP catches it, marks the result as an error, and the next tool call on the
same client still works. There is no process crash and no disconnect.

### The real problem, which is worth fixing

That test output shows two genuine defects, both narrower than the comment and both
worth the fix it proposes:

1. **The raw exception message reaches the client.** `DESIGN.md` states these tools
   "do not reveal raw exceptions or Open Library response JSON", and the
   `LookupUnavailable` path is careful about it. An unexpected error bypasses that
   promise and leaks internal text straight to an AI client.
2. **`structured_content` is `None`.** Our own `app/mcp_client._call_tool` requires
   a dict and raises `MCPUnavailable` when it is missing. The web app survives, by
   falling back to the seed, but it gets there through a broken envelope rather
   than the `unavailable` status that exists for exactly this case.

### Plan

1. Broaden the `except` in `_search_result` and `get_book_details` to catch
   `Exception` after the existing `LookupUnavailable` clause, return the standard
   `_unavailable()` result, and `logger.exception` the detail server-side so it is
   diagnosable without being disclosed.
2. Add a logger to `mcp_server/server.py`; it has none.
3. Keep `LookupUnavailable` as its own clause. A catalogue outage is expected and a
   bug in our mapping code is not, and the log should say which happened.

### Files

`mcp_server/server.py`.

### Tests

Add to `tests/test_mcp_server.py` and `tests/test_search_paging.py`:

- a search function raising `RuntimeError` yields `status: "unavailable"`, with
  structured content present and the raw message absent from the text;
- the same for `get_book_details`;
- `app.mcp_client` turns that into `MCPUnavailable`, and `lookup` then falls back to
  the seed.

### Done when

No unexpected exception can leave a tool without a structured `unavailable`
envelope, and no internal message appears in tool text.

## Item 5 - `_format_book` duplicates the field list

Emma Zhou, marked nitpick. Agreed as stated.

### What

`mcp_server/server.py` builds a book's fields twice: `_format_book` writes the
readable lines and `_book_payload` writes the structured dict. Adding a publisher
means editing both, and they can drift. The newline is hardcoded in the `join`.

### Plan

Define the field order once as `(label, value)` pairs, then derive both outputs
from it: the readable text by formatting the labels, the payload by keying on a
machine name. One list, two renderings, and a new field is one edit.

The suggested `LINE_BREAK = "\n"` constant is not worth adding. `"\n".join(...)` is
idiomatic Python and reads more clearly than an indirection, and once the field list
is shared there is only one place the newline appears. Recording the disagreement.

### Files

`mcp_server/server.py`.

### Tests

`tests/test_mcp_server.py` and `tests/test_author_search.py` already assert on both
the readable text and the structured payload. They should pass unchanged; that is
the point of the refactor. Add one test asserting the two outputs describe the same
field set, so a future field cannot be added to only one.

### Done when

Field names and order are declared once, and the existing assertions still pass.

## Item 6 - An `id` field in `seed/books.json`

Emma Zhou, marked nitpick. **Recommend not doing this.** The underlying observation
is correct but the conclusion does not fit what this file is.

### The comment

Each entry lacks an auto-increment unique id and relies on ISBN as the unique
identifier. One book can have several editions with different ISBNs, so ISBN cannot
be a stable primary key, and primary-key conflicts are likely during CRUD.

### Why the fix does not apply here

`seed/books.json` is not a table and never becomes rows carrying its own
identifiers. It is the offline catalogue that stands in for Open Library when the
network is unavailable. `app/lookup.py:84-88` reads exactly four keys from each
entry and builds a `BookDetails`, the same value type the live catalogue produces.
An `id` added to the file would be read by nothing.

Books already have a primary key. `app/db.py` gives the `books` table a SQLite
`INTEGER PRIMARY KEY`, assigned on insert. Adding ids to the seed would create a
second numbering that means nothing to the database, which is worse than having
none.

The "primary-key conflict" risk therefore does not exist as described: the seed
supplies metadata, not keys.

### The real point inside the comment, which we should record

"One book can have several editions with different ISBNs" is true and does affect
us, through `identity_key`, which is `isbn:<normalised>`. Two editions of one work
are two tracked rows. That is deliberate, not an oversight - `CLAUDE.md` states
"Allow books with the same title when their ISBNs are different" - and it is what
lets someone track the paperback they own rather than an abstract work.

The cost is visible in the paged results: `author=J. K. Rowling` returns 421
results, many of them editions and translations of the same seven novels. Grouping
editions under a work would be a genuine improvement, and Open Library exposes a
work key (`key`, e.g. `/works/OL82563W`) that would support it.

That is a product change, not a nitpick. Proposal: reply to the comment explaining
why an `id` in the seed would be inert, raise edition-grouping as a separate
backlog item against `DESIGN.md` section 7.7, and change nothing now.

### Done when

The comment has a written reply and an edition-grouping item exists in
`DESIGN.md`'s future work.

## Sequencing

1. **Item 2** - finish the browser check, then commit and push. Everything else
   touches the same files.
2. **Item 1** - the only real defect. Small, self-contained, user-visible.
3. **Item 4** - small, and makes the remaining work easier to debug.
4. **Item 3** - depends on nothing, but is smaller than it looked once regraded.
5. **Item 5** - refactor, safest last, guarded by existing assertions.
6. **Item 6** - a written reply and a backlog entry, no code.

Items 1 and 3-5 are independent and can be split across the team. All of them
should be one commit each on a feature branch, per `CLAUDE.md`.

## Timing and ownership

M3 code freeze is **2026-08-10 (Monday)**; everything here should be merged and the
deployed URL verified before then.

| Item | Owner | Target |
|---|---|---|
| 2 - ship author search/paging | TBD - assign | End of 2026-08-07 |
| 1 - card error handling | TBD - assign | 2026-08-08 |
| 4 - MCP generic exceptions | TBD - assign | 2026-08-08 |
| 3 - MCP input normalisation | TBD - assign | 2026-08-09 |
| 5 - `_format_book` refactor | TBD - assign | 2026-08-09 |
| 6 - reply + backlog entry | TBD - assign | 2026-08-09 |

This file should be committed to the repository (repo root as `PLAN.md`, or under
`docs/`) before the code freeze, as evidence of processing the review feedback.

## Out of scope

- A JavaScript test runner. Item 1 needs one to be tested properly, and choosing it
  is a team decision, not part of this fix.
- Grouping editions under a work. Raised in Item 6, deliberately deferred.
- ~~The stale parts of `README.md` that predate the MCP server, which still say the
  MCP server "has not yet been completed"~~. Resolved on 2026-08-06 in PR #13
  (`docs/m2-evidence`, merged to `main` as `e842386`): README.md and CLAUDE.md now
  reflect the MCP implementation, and the CI workflow, Semgrep report, and AI usage
  log were added.

## Review claim summary

| Item | Review severity | Our assessment | Fixing? |
|---|---|---|---|
| Card listener error handling (ours) | - | Real defect | Yes |
| MCP input sanitisation | critical | Real gap, but no request-integrity risk | Yes, regraded |
| MCP generic exceptions | suggestion | Real gap; stated cause and crash claim both wrong | Yes, different reason |
| `_format_book` duplication | nitpick | Agreed, minus the newline constant | Yes, partly |
| `id` in `seed/books.json` | nitpick | Does not apply to this file | No, with a reply |
