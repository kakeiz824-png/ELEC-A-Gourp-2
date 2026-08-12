# Tags (Multi-label) Design — Shelf Life

**Date:** 2026-08-11
**Status:** Approved by user (option A: multi-tags; mixed free-text + suggestions; global filter bar; inline card editing)

## Goal

Let users attach multiple free-form labels (e.g. `sci-fi`, `寒假书单`) to books, filter shelves by a tag, and edit tags inline on a book card.

## Data model

- `tags`: `id` INTEGER PK, `name` TEXT NOT NULL UNIQUE, `created_at` TEXT.
- `book_tags`: `book_id` INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE, `tag_id` INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE, PRIMARY KEY (book_id, tag_id).
- Created in `app/db.py` schema; existing databases get the tables via the same migration path.

## API

- `GET /tags` — list `{id, name, count}` for every tag, ordered by name.
- `GET /books?tag=NAME` — list books filtered by tag (combinable with `?shelf=`).
- `PUT /books/{id}/tags` — body `{"tags": ["sci-fi", "2026"]}`; full replacement. Normalization: strip, drop blanks, dedupe, max 20 tags, each max 50 chars. Deletes orphan tags with no remaining books.
- Deleting a book cascades `book_tags`; orphan tags are removed.

## UI

- Tag filter bar above the shelves: "All" plus one chip per tag (`name (count)`); click to filter all three shelves, click again to clear.
- Book cards show tag chips; a "Tags" button expands an inline editor (text input + suggestions of existing tags; Enter/click adds; selected chips removable; Save persists via `PUT`).
- Styles follow existing CSS variables. app.js cache version bumped.

## Testing

- API: create/replace tags, dedupe/limit/blank validation, filter by tag (+ shelf), cascade delete, orphan cleanup, 404 on missing book.
- Template: filter bar present, card tag area present, app.js version bumped.
- Full suite stays green.