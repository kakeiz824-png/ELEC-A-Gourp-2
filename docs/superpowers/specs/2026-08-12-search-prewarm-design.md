# Search Warm-up & Instant Feedback — Design

Date: 2026-08-12
Repo: ELEC-A-Gourp-2 (main, 22c18be)
Status: Approved (方案二)

## Goal

Make the demo's live searches feel instant. Today, a first-time keyword hits
Open Library live (2–6s); repeated keywords are already served by the in-memory
5-minute cache. The fix warms the cache for the demo queries and keeps old
results visible while a search runs.

## Scope

- `static/app.js`: warm-up + local search cache + stale-while-revalidate.
- `templates/index.html`: bump the `app.js?v=` cache-buster.
- No backend, database, or test changes.

## Changes

1. **Warm-up (client-side).** After login, fire-and-forget requests warm the
   server cache for: `title=Three Body`, `author=Liu Cixin`, `title=The Hobbit`,
   and `/authors?name=Liu Cixin`. Failures are silent.
2. **Instant feedback.** On submit:
   - If the same (mode, query) is in `localStorage` (last 8 searches): render
     the cached results immediately, then revalidate in the background.
   - Otherwise: keep current results on screen and show "Searching for …".
   The author panel is cleared either way; the page never goes blank.
3. **Cache-buster.** `app.js?v=20260812-recommendations` →
   `?v=20260813-prewarm` so browsers fetch the new file.

## Validation

- `node --check static/app.js`
- `pytest` (285 passed, unchanged)
- Local server smoke: homepage references the new `app.js` version; search
  endpoints still answer.

## Deploy

Commit to `main`, push to origin, then Render → Manual Deploy → latest commit.
