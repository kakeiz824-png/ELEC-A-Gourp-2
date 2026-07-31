---
name: add-endpoint
description: Scaffold a new API endpoint in the Shelf Life app following this project's conventions (router + Pydantic model + service + test).
---

Add a new API endpoint. Endpoint description: $ARGUMENTS

Follow the existing conventions in this codebase. Study `app/routers/books.py` and
`tests/test_books.py` first, then mirror their style exactly.

Steps:

1. **Route handler** — Add the endpoint to the appropriate file in `app/routers/`
   (create a new router module only if it is a genuinely new resource). Use
   `APIRouter(prefix=..., tags=[...])`, take the database via
   `connection: sqlite3.Connection = Depends(get_db)`, and declare a
   `response_model`. If you create a new router, register it in `app/main.py`
   with `app.include_router(...)`.

2. **Data structures** — Add or extend the Pydantic models in `app/models.py`
   for the request body and response shape. Do not return raw sqlite rows;
   convert them the way `row_to_book` does.

3. **Business logic** — If the endpoint does anything beyond a trivial query,
   put the logic in `app/services/`, not in the router. Routers handle HTTP;
   services hold the rules.

4. **Errors** — Raise `HTTPException` with the right status code for missing or
   invalid data (e.g. 404 for not found), following the `fetch_book` pattern.

5. **Test** — Add a test in `tests/` mirroring `tests/test_books.py`
   (use the fixtures in `tests/conftest.py`). Cover the success case and at
   least one error case.

6. **Docs** — Update `README.md` and, if the endpoint changes the design,
   `DESIGN.md`.

7. **Verify** — Run the `/test` skill to execute the suite, then run the
   `/review` skill over the new changes. Fix anything they surface before
   reporting done.
